"""
Shared Collection Example - Cross-Service Data Access

This example demonstrates how two services can share data:
- Service A owns and writes to a collection
- Service B reads from Service A's collection (with permission)
"""
import asyncio
from datetime import datetime, timedelta
from shared.utils.data_client import AOLDataClient

class ServiceA:
    """Producer service that owns and writes data"""
    
    def __init__(self):
        self.data_client = AOLDataClient(
            aol_core_endpoint="aol-core:50051",
            service_name="service-a"
        )
    
    async def setup(self):
        """Setup collections and grant access to Service B"""
        # Create our collection
        await self.data_client.request_collection(
            name='metrics',
            schema_hint={
                'metric_name': 'string',
                'value': 'number',
                'timestamp': 'datetime'
            },
            indexes=[
                {'fields': ['metric_name', 'timestamp'], 'type': 'compound'}
            ]
        )
        
        # Grant read access to Service B
        await self.data_client.grant_access(
            collection='metrics',
            target_service='service-b',
            permission='read'
        )
        print("Service A: Collection created and access granted to Service B")
    
    async def store_metric(self, name, value):
        """Store a metric"""
        doc_id = await self.data_client.insert('metrics', {
            'metric_name': name,
            'value': value,
            'timestamp': datetime.utcnow().isoformat()
        })
        print(f"Service A: Stored metric {name}={value}")
        return doc_id

class ServiceB:
    """Consumer service that reads Service A's data"""
    
    def __init__(self):
        self.data_client = AOLDataClient(
            aol_core_endpoint="aol-core:50051",
            service_name="service-b"
        )
    
    async def analyze_metrics(self, metric_name, hours=24):
        """
        Read and analyze Service A's metrics
        
        Note: Service B's manifest.yaml must declare:
        dataRequirements:
          accessRequests:
            - collection: "service-a.metrics"
              permission: "read"
              reason: "Analytics on service metrics"
        """
        since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        # Query Service A's collection (full namespaced name)
        metrics = await self.data_client.query(
            collection='service-a.metrics',  # Note the full namespace
            filters={
                'metric_name': metric_name,
                'timestamp': {'$gte': since}
            },
            sort={'timestamp': 'asc'}
        )
        
        if not metrics:
            print(f"Service B: No metrics found for {metric_name}")
            return None
        
        # Calculate statistics
        values = [m['value'] for m in metrics]
        stats = {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values)
        }
        
        print(f"Service B: Analyzed {metric_name} (last {hours}h):")
        print(f"  Count: {stats['count']}")
        print(f"  Min: {stats['min']:.2f}")
        print(f"  Max: {stats['max']:.2f}")
        print(f"  Avg: {stats['avg']:.2f}")
        
        return stats

async def main():
    """Demonstrate cross-service data sharing"""
    service_a = ServiceA()
    service_b = ServiceB()
    
    # Setup Service A
    await service_a.setup()
    
    # Service A writes metrics
    print("\n=== Service A: Writing Metrics ===")
    for i in range(10):
        await service_a.store_metric('api_response_time', 100 + (i * 10))
        await asyncio.sleep(0.1)
    
    # Service B analyzes metrics
    print("\n=== Service B: Analyzing Metrics ===")
    stats = await service_b.analyze_metrics('api_response_time', hours=24)
    
    # Service B tries to write (should fail - only has read permission)
    print("\n=== Service B: Attempting to Write (Should Fail) ===")
    try:
        await service_b.data_client.insert('service-a.metrics', {
            'metric_name': 'unauthorized',
            'value': 999,
            'timestamp': datetime.utcnow().isoformat()
        })
        print("Service B: Write succeeded (unexpected!)")
    except Exception as e:
        print(f"Service B: Write failed as expected: {e}")

if __name__ == '__main__':
    asyncio.run(main())

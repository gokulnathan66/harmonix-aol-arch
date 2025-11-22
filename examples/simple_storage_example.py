"""
Simple Storage Example - AOL Data Client Usage

This example demonstrates basic CRUD operations using the AOL Data Client.
Service stores application events and retrieves them with filters.
"""
import asyncio
import uuid
from datetime import datetime
from shared.utils.data_client import AOLDataClient

class SimpleStorageExample:
    """Example service demonstrating basic data storage"""
    
    def __init__(self):
        # Initialize data client (connects to AOL-Core, not database directly)
        self.data_client = AOLDataClient(
            aol_core_endpoint="aol-core:50051",
            service_name="example-service"
        )
    
    async def setup(self):
        """Initialize collections declared in manifest.yaml"""
        # Request the 'events' collection
        # This collection should be declared in manifest.yaml
        collection_id = await self.data_client.request_collection(
            name='events',
            schema_hint={
                'event_id': 'string',
                'event_type': 'string',
                'timestamp': 'datetime',
                'data': 'object'
            },
            indexes=[
                {'fields': ['timestamp'], 'type': 'ascending'},
                {'fields': ['event_type'], 'type': 'ascending'}
            ]
        )
        print(f"Collection 'events' initialized: {collection_id}")
    
    async def log_event(self, event_type, data):
        """Store an event in the database"""
        event = {
            'event_id': str(uuid.uuid4()),
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'data': data
        }
        
        doc_id = await self.data_client.insert('events', event)
        print(f"Stored event {event['event_id']}: {doc_id}")
        return doc_id
    
    async def get_recent_events(self, event_type=None, limit=10):
        """Retrieve recent events, optionally filtered by type"""
        filters = {}
        if event_type:
            filters['event_type'] = event_type
        
        events = await self.data_client.query(
            collection='events',
            filters=filters,
            sort={'timestamp': 'desc'},
            limit=limit
        )
        
        print(f"Retrieved {len(events)} events")
        return events
    
    async def count_events_by_type(self, event_type):
        """Count events of a specific type"""
        events = await self.data_client.query(
            collection='events',
            filters={'event_type': event_type}
        )
        return len(events)

async def main():
    """Run the example"""
    example = SimpleStorageExample()
    
    # Setup
    await example.setup()
    
    # Insert some events
    await example.log_event('user.login', {
        'user_id': '12345',
        'ip_address': '192.168.1.1'
    })
    
    await example.log_event('user.logout', {
        'user_id': '12345',
        'duration': 3600
    })
    
    await example.log_event('user.login', {
        'user_id': '67890',
        'ip_address': '192.168.1.2'
    })
    
    # Query events
    print("\n=== All Recent Events ===")
    all_events = await example.get_recent_events(limit=10)
    for event in all_events:
        print(f"  {event['timestamp']} - {event['event_type']}")
    
    print("\n=== Login Events Only ===")
    login_events = await example.get_recent_events(event_type='user.login')
    for event in login_events:
        print(f"  {event['data']}")
    
    print("\n=== Event Count ===")
    login_count = await example.count_events_by_type('user.login')
    print(f"Total logins: {login_count}")

if __name__ == '__main__':
    asyncio.run(main())

run-core-monitor:
	cd core-monitor && npm run dev

run-aol-core:
	cd aol-core && poetry run python main.py

clean:
	rm -rf .venv
	poetry cache clean --all

run-consul:

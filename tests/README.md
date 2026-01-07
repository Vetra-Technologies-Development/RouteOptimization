# Tests

This directory contains tests for the Route Optimization API.

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements.txt
```

Or install just the test dependencies:

```bash
pip install pytest httpx pytest-asyncio
```

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_loadboard_endpoint.py
```

### Run with Verbose Output

```bash
pytest -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest --cov=app --cov-report=html
```

## Test Structure

- `test_loadboard_endpoint.py` - Tests for LoadBoard Network endpoints (`/loadboard/post_loads` and `/loadboard/remove_loads`)

## Test Coverage

The tests cover:

1. **Successful Operations**
   - Posting loads successfully
   - Removing loads successfully
   - Handling multiple loads

2. **Error Handling**
   - Supabase not configured
   - Invalid XML format
   - Missing required fields
   - Service errors

3. **Edge Cases**
   - Minimal XML (only required fields)
   - No loads found
   - Invalid JSON requests

## Mocking

The tests use `unittest.mock` to mock:
- Supabase service calls
- LoadBoard service methods
- Configuration checks

This allows tests to run without requiring actual Supabase credentials or database connections.

## Example Test Run

```bash
$ pytest tests/test_loadboard_endpoint.py -v

tests/test_loadboard_endpoint.py::TestPostLoadsEndpoint::test_post_loads_success PASSED
tests/test_loadboard_endpoint.py::TestPostLoadsEndpoint::test_post_loads_supabase_not_configured PASSED
tests/test_loadboard_endpoint.py::TestPostLoadsEndpoint::test_post_loads_minimal_xml PASSED
...
```


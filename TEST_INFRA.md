# E2E Test Infra: BigQuery Release Notes Web Application

## Test Philosophy
- Opaque-box, requirement-driven. No dependency on implementation design.
- Mocking: Uses a local mock RSS server to simulate success and failure feed responses.
- Methodology: Category-Partition + BVA + Pairwise + Workload Testing.

## Feature Inventory
| # | Feature | Source | Tier 1 | Tier 2 | Tier 3 |
|---|---------|--------|:------:|:------:|:------:|
| 1 | Serve Frontend | R1 / R2 | 5      | 5      | ✓      |
| 2 | Retrieve Release API | R1 | 5      | 5      | ✓      |
| 3 | Parse Feed Content | R1 | 5      | 5      | ✓      |
| 4 | Refresh Feed & Spinner | R3 | 5      | 5      | ✓      |
| 5 | Tweet Share Intent | R4 | 5      | 5      | ✓      |
| 6 | API Error Handling | R1 | 5      | 5      | ✓      |

## Test Architecture
- Test runner: Python `pytest` using `playwright` or `selenium` (or pure request-based/jsdom-based tests if simplified browser control is preferred).
- Mock RSS server: A simple python mock feed server that serves custom test RSS files.
- Test layout:
  - `tests/conftest.py`: pytest configuration and server start/stop fixtures.
  - `tests/test_tier1_feature.py`: Feature coverage (happy-paths, 30 tests).
  - `tests/test_tier2_boundary.py`: Boundary and corner cases (error conditions, extreme feeds, empty feeds, invalid fields, 30 tests).
  - `tests/test_tier3_pairwise.py`: Pairwise interactions of features (6 tests).
  - `tests/test_tier4_workloads.py`: Application-level scenarios (5 workloads).

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | Standard User Flow | Serve frontend -> API Success -> Render list -> Click Refresh -> List Updates | Medium |
| 2 | Sharing Flow | Serve frontend -> API Success -> Click Tweet Share on card -> Check intent URL | Medium |
| 3 | Failure/Recovery Flow | Serve frontend -> API Error (feed down) -> Show error -> Feed recovered -> Refresh | High |
| 4 | No Updates Flow | Serve frontend -> API returns empty list -> Correct empty message shown -> Refresh | Medium |
| 5 | Content Rich Feed Flow | Serve frontend -> API returns entries with heavy HTML -> Rendered safely | High |

## Coverage Thresholds
- Tier 1: 30 test cases
- Tier 2: 30 test cases
- Tier 3: 6 test cases
- Tier 4: 5 realistic application scenarios
- Total minimum: 71 test cases

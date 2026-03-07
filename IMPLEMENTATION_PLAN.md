# Implementation Plan

> This file is managed by Ralph. It tracks progress across loop iterations.
> Delete this file and run `./ralph.sh plan` to regenerate.

## Task: Add ChromosomeSpec Unit Tests

Create comprehensive unit tests for ChromosomeSpec, IntegerChromosomeSpec, and DoubleChromosomeSpec classes.

**Target file:** `src/test/java/com/verlumen/tradestream/discovery/ChromosomeSpecTest.java`

## Completed

### 1. Create test file and BUILD target
- [x] Create `ChromosomeSpecTest.java` in `src/test/java/com/verlumen/tradestream/discovery/`
- [x] Add `java_test` target to `src/test/java/com/verlumen/tradestream/discovery/BUILD`
  - Dependencies: `chromosome_spec`, `guava`, `jenetics`, `junit`, `truth`

### 2. Implement ChromosomeSpec static factory method tests
- [x] Test `ofInteger(min, max)` creates valid IntegerChromosomeSpec
  - Verify returned object is instanceof IntegerChromosomeSpec
  - Verify range is correctly set
- [x] Test `ofDouble(min, max)` creates valid DoubleChromosomeSpec
  - Verify returned object is instanceof DoubleChromosomeSpec
  - Verify range is correctly set

### 3. Implement IntegerChromosomeSpec tests
- [x] Test `getRange()` returns correct closed range with min/max values
- [x] Test `createChromosome()` returns IntegerChromosome
  - Verify type is IntegerChromosome
  - Verify bounds match the range (lowerEndpoint, upperEndpoint)
- [x] Test chromosome gene values are within specified range
  - Create chromosome, check gene values are >= min and <= max

### 4. Implement DoubleChromosomeSpec tests
- [x] Test `getRange()` returns correct closed range with min/max values
- [x] Test `createChromosome()` returns DoubleChromosome
  - Verify type is DoubleChromosome
  - Verify bounds match the range (lowerEndpoint, upperEndpoint)
- [x] Test chromosome gene values are within specified range
  - Create chromosome, check gene values are >= min and <= max

### 5. Build and verify tests pass
- [x] Run `bazel build //src/test/java/com/verlumen/tradestream/discovery:ChromosomeSpecTest`
- [x] Run `bazel test //src/test/java/com/verlumen/tradestream/discovery:ChromosomeSpecTest`
- [x] Verify all tests pass

## In Progress

_No tasks in progress._

## Pending (Priority Order)

_All tasks completed._

## Test Structure Reference

Based on existing test patterns (e.g., `GenotypeConverterImplTest.java`):
- Use JUnit 4 with `@RunWith(JUnit4.class)`
- Use Google Truth for assertions (`assertThat`)
- Use static imports for Truth and Guava
- Follow naming convention: `methodName_condition_expectedResult`

## Dependencies for BUILD target

```python
java_test(
    name = "ChromosomeSpecTest",
    srcs = ["ChromosomeSpecTest.java"],
    deps = [
        "//src/main/java/com/verlumen/tradestream/discovery:chromosome_spec",
        "//third_party/java:guava",
        "//third_party/java:jenetics",
        "//third_party/java:junit",
        "//third_party/java:truth",
    ],
)
```

## Acceptance Criteria

- [x] All tests pass
- [x] Tests cover static factory methods (`ofInteger`, `ofDouble`)
- [x] Tests verify range constraints
- [x] Tests verify chromosome creation and bounds

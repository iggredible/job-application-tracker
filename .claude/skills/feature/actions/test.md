# Test

1. Read `docs/features/current.md` and the spec.
2. Run `make test` and `make lint`. Report the results.
3. For each test the spec asks for, name the test that covers it. List any that are missing, then write them.
4. Check that no test makes a network call and that all AI calls are mocked.
5. For new endpoints, confirm they appear in `/docs` with correct request and response schemas.
6. List the manual checks for the user to do in the browser, as numbered steps with the expected result of each.
7. Suggest one way to break the feature on purpose that a test should catch, such as removing a guard or adding an invalid transition. Do not make the change.

Do not change application code in this action except to fix a failing check.

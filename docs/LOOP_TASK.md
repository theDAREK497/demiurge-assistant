# Loop Task

## Goal

Run a short, repeatable implementation loop that improves the project without
losing the stable manual-testing path in `/app/`.

Current local LLM target:

- Base URL: `http://127.0.0.1:1234/v1`
- Model: `gemma-4-e4b-uncensored-hauhaucs-aggressive`

## Working Loop

1. Read `docs/CONTEXT.md` first.
2. Pick one small vertical slice from `docs/NEXT_IMPLEMENTATIONS_PLAN.md`.
3. Implement the backend part first when schema or persistence changes are
   needed.
4. Expose the change in the stable `/app/` UI if it affects manual testing.
5. Test with:
   - `python -m pytest`
   - `python -m compileall src tests`
6. Run a quick manual check through `/app/`.
7. Update `docs/CONTEXT.md` if the user flow, setup, or important known issues
   changed.
8. Move to the next slice only after the current one is stable.

## Definition Of Done For One Loop

- the feature works through the API;
- the feature is reachable or testable from the current manual-testing flow;
- automated checks pass;
- the new behavior is documented if it changes how the project should be used.

## Constraints

- Keep `/app/` as the primary manual-testing surface.
- Prefer incremental work over broad rewrites.
- Do not assume cloud APIs; local OpenAI-compatible LM Studio remains the main
  target.
- Preserve master/player visibility and proposal-review safety.

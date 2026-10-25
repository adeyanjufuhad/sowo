# Sowo API rules

- The AI only understands the buyer and writes the reply. Our code decides every price, total, stock change and payment.
- The model must NEVER see `floor_price`. Never put it in prompts, tool outputs, logs shown to the model, or any hint text.
- Money is integer kobo everywhere.
- Secrets only in `.env`. Never commit them.
- Never edit `docs/api-contract.md`. If the code needs a change, write it to `apps/api/CONTRACT_NOTES.md` instead.
- Money and haggling logic needs unit tests. Run tests with `pytest`. Lint with `ruff check`.

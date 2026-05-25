# Knowledge Base — Excel files

Drop your `.xlsx` files in this folder. On startup, Kevin reads:
- every sheet
- up to 200 rows per sheet
- caches the result in `knowledge_base.json` at the repo root

To force a reload after editing/adding an Excel file:
1. Delete `knowledge_base.json`, OR
2. Hit `POST /api/reload_knowledge` (requires login)

> Files in this folder are part of Kevin's brain. Review what you commit publicly — anything you put here goes into Claude/Gemini's context.

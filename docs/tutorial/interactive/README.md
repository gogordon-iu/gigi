# Interactive Gigi explorer

`docs/tutorial/gigi_explorer.html` is the interactive replacement for the two static
figures (`src_structure.*` and `story_game_flow.*`). It is a single self-contained file,
so you can open it by double-clicking. It needs no server and no internet.

| View | What you can do |
|---|---|
| **Code Map** | Zoomable map of every package, file, class and function in `src/gigi`. **Click** a box to dive in; **Esc** or right-click dives out; the **wheel** zooms; **drag** pans. Labels appear and disappear with the zoom level, so text is always readable. Selecting a file draws its `gigi` imports (blue) and importers (orange). ★ marks code used by the Story Game. |
| **Story Game Flow** | The 7 phases as cards. Click a phase to get its sequence diagram, then click a step to see an explanation and the real source code (highlighted). Use **← / →** to step through all 74 calls. |

Both views share a side panel with the source code and cross-links, plus a search box (`/`).
Deep links work too, for example `gigi_explorer.html#map=core/robot.py:Character.run_character`
or `gigi_explorer.html#flow=4.7`.

## Rebuilding

```bash
python docs/tutorial/interactive/build_explorer.py
```

| File | Role |
|---|---|
| `build_explorer.py` | Parses `src/gigi` with `ast`, resolves the code references in the flow, and inlines everything into the HTML file |
| `explorer_template.html` | The app itself (vanilla JS + SVG, no dependencies) |
| `story_flow.json` | Hand-written walkthrough content: phases, steps, explanations and code refs such as `core/robot.py:Character.listen_backchannel` |

The Code Map always reflects the current code. If a function named in `story_flow.json` is
renamed or moved, the build prints a warning and exits with code 1.

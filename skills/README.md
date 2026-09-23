# Claude skills for Akvo MIS

| Skill | Use it for |
|---|---|
| [`akvo-mis-workspace-from-data`](akvo-mis-workspace-from-data/SKILL.md) | Turning a spreadsheet into a working MIS workspace: analysing the data, proposing forms and an administration hierarchy, creating the workspace, and loading the records |

## Install

**Claude Code.** Copy or symlink the skill folder into `~/.claude/skills/` for
personal use, or into a project's `.claude/skills/`:

```bash
ln -s "$PWD/skills/akvo-mis-workspace-from-data" ~/.claude/skills/
```

**Claude.ai and Claude Desktop.** Zip the folder so that `SKILL.md` sits at the
root of the zip's single top-level folder:

```bash
cd skills && zip -r akvo-mis-workspace-from-data.zip akvo-mis-workspace-from-data -x '*/__pycache__/*'
```

Then upload it under *Settings → Capabilities → Skills*. The *Code execution*
setting must be on.

The Claude.ai sandbox may block outbound network traffic. When it does, the skill
still analyses the data and writes the plan, but it then hands over the
folder with the commands (`python mis.py --plan plan.json register`, then
`apply`) for the user to run on their own machine. To let Claude run the
setup itself, allow `*.mis.akvotest.org` / `*.mis.akvo.org` in the
organisation's network egress settings.

## Testing locally

Point the plan at the docker stack (`"base_domain": "app.local",
"scheme": "http"`) and pass `--connect http://localhost:8000` to `mis.py`.
The activation email appears in Mailpit at http://localhost:8025. Instead of
clicking its link, run `mis.py activate <link-or-token>`.

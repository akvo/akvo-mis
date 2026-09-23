# Claude skills for Akvo MIS

| Skill | Use it for |
|---|---|
| [`akvo-mis-workspace-from-data`](akvo-mis-workspace-from-data/SKILL.md) | Turning a spreadsheet into a working MIS workspace: analysing the data, proposing forms and an administration hierarchy, creating the workspace, and loading the records |

## How it works

1. **Share the data.** Give Claude the Excel or CSV file and say you want an MIS workspace from it.
2. **Review the proposal.** Claude analyses the data and shows a readable plan. It covers:
   - the administration tree,
   - each form, question by question,
   - which column feeds which question,
   - what will not be loaded, and why.

   Ask for changes until it looks right, then approve it.
3. **Give the workspace details.** You provide your email, the subdomain (for example `who` for `who.mis.akvotest.org`) and your name. The test environment is used unless you ask for production.
4. **Activate.** Claude creates the workspace with a temporary password, and MIS emails you an activation link. Click it and tell Claude when you're done. If a *Configure workspace* page opens, leave it: Claude fills that in from the plan.
5. **Build.** Claude sets up the administration and the forms, then loads the data. If Claude can't reach MIS from where it runs, it gives you the commands to run yourself.
6. **Take over.** Log in with the temporary password and change it via *Forgot password*. Claude also gives you:
   - the number of records loaded per form,
   - any rows that could not be loaded.

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

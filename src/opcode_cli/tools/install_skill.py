from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from opcode_cli.skills import SkillDefinition, parse_skill
from opcode_cli.tools.base import BaseTool, ToolResult


class InstallSkillTool(BaseTool):
    """从 URL 安装 Skill（系统级，不受白名单约束）。"""

    name = "install_skill"
    description = (
        "Install a skill from a URL. "
        "Supports raw markdown skill files and skills.sh URLs. "
        "The skill is saved to the user skills directory and registered for use."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": (
                    "URL to the skill markdown file. "
                    "Can be a skills.sh URL (e.g. https://www.skills.sh/anthropics/skills/frontend-design) "
                    "or a raw markdown URL."
                ),
            },
        },
        "required": ["url"],
    }
    system_level: bool = True

    def __init__(
        self,
        skills_loader: object,
        skill_registry: object,
        user_skills_dir: Path,
    ) -> None:
        self._skills_loader = skills_loader
        self._skill_registry = skill_registry
        self._user_skills_dir = user_skills_dir

    async def execute(self, url: str) -> ToolResult:
        import urllib.request

        # Step 1: Try to fetch the raw content
        raw_content = None
        tried_urls = [url]

        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "opcode-skill-installer/1.0"}
            )
            resp = urllib.request.urlopen(req, timeout=30)
            content_type = resp.headers.get("Content-Type", "")
            raw_content = resp.read().decode("utf-8")

            # If HTML, try skills.sh → GitHub raw conversion
            if "text/html" in content_type:
                raw_content = None  # reset, will try GitHub fallback
        except Exception as e:
            return ToolResult(
                success=False,
                content="",
                error=f"Failed to fetch URL: {e}",
            )

        # Step 2: If HTML or failed, try skills.sh → GitHub raw URL
        if raw_content is None or not raw_content.startswith("---"):
            gh_url = self._skills_sh_to_github_raw(url)
            if gh_url:
                tried_urls.append(gh_url)
                try:
                    req = urllib.request.Request(
                        gh_url, headers={"User-Agent": "opcode-skill-installer/1.0"}
                    )
                    resp = urllib.request.urlopen(req, timeout=30)
                    raw_content = resp.read().decode("utf-8")
                except Exception:
                    raw_content = None

        # Step 3: Check if we got valid frontmatter markdown
        if not raw_content:
            return ToolResult(
                success=False,
                content="",
                error=(
                    f"Could not retrieve raw skill content from:\n"
                    f"{chr(10).join(tried_urls)}\n\n"
                    "Try providing a direct raw markdown URL."
                ),
            )

        if not raw_content.startswith("---"):
            return ToolResult(
                success=False,
                content="",
                error="The URL does not point to a valid skill markdown file (missing frontmatter).",
            )

        # Step 4: Save to a temp location and parse
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(raw_content)
            tmp_path = Path(f.name)

        try:
            defn = parse_skill(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

        if defn is None:
            return ToolResult(
                success=False,
                content="",
                error="Failed to parse skill definition from the markdown content.",
            )

        # Step 5: Save to user skills directory
        self._user_skills_dir.mkdir(parents=True, exist_ok=True)
        skill_file = self._user_skills_dir / f"{defn.name}.md"

        # Avoid overwriting existing skills
        try:
            self._skill_registry.get(defn.name)
            return ToolResult(
                success=False,
                content="",
                error=f"Skill '{defn.name}' is already registered.",
            )
        except KeyError:
            pass

        skill_file.write_text(raw_content, encoding="utf-8")

        # Step 6: Reload and register
        fresh_defn = self._skills_loader.load_one(defn.name)
        if fresh_defn is None:
            skill_file.unlink(missing_ok=True)
            return ToolResult(
                success=False,
                content="",
                error="Failed to reload the skill after saving.",
            )

        self._skill_registry.register(fresh_defn)

        return ToolResult(
            success=True,
            content=(
                f"Skill '{fresh_defn.name}' installed successfully.\n"
                f"Description: {fresh_defn.description}\n"
                f"Saved to: {skill_file}\n"
                f"Use /{fresh_defn.name} to run it."
            ),
        )

    @staticmethod
    def _skills_sh_to_github_raw(url: str) -> str | None:
        """Convert skills.sh URL to GitHub raw URL.

        Pattern: https://www.skills.sh/{org}/{repo}/{skill-name}
        → https://raw.githubusercontent.com/{org}/{repo}/main/skills/{skill-name}/SKILL.md
        """
        parsed = urlparse(url)
        if "skills.sh" not in parsed.netloc and "skills.sh" not in parsed.hostname:
            return None

        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 3:
            return None

        org, repo, skill_name = parts[0], parts[1], parts[2]
        return (
            f"https://raw.githubusercontent.com/"
            f"{org}/{repo}/main/skills/{skill_name}/SKILL.md"
        )

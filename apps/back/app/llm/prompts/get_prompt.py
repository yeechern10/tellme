from pathlib import Path
import re

PROMPT_ROOT_DIR = Path(__file__).parent

def _version_key(stem: str) -> tuple[int, int, int, int]:
    """
    Convert a version string into a tuple for sorting.
    
    Args:
        stem (str): The stem of the filename, which is expected to be a version string.

    Returns:
        tuple[ is_semver(int), major(int), minor(int), patch(int)]: A tuple that can be used for sorting version strings.
            - is_semver: 1 if the version string is a valid semantic version, 0 otherwise.
            - major: The major version number.
            - minor: The minor version number.
            - patch: The patch version number.
    """
    m = re.fullmatch(r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", stem.strip(), re.IGNORECASE)
    if not m:
        return (0, 0, 0, 0)  # Default to a low version if parsing fails
    major, minor, patch = (int(g) if g is not None else 0 for g in m.groups())
    return (1, major, minor, patch)

def get_prompt(prompt_name: str, version: str = "latest") -> str:
    """
    Get the prompt text from a file.

    Args:
        prompt_name (str): The name of the prompt file (without extension).
        version (str): The version of the prompt. Defaults to "latest".

    Returns:
        str: The content of the prompt file.

    Raises:
        FileNotFoundError: If the specified prompt file does not exist.
    """

    prompt_dir = PROMPT_ROOT_DIR / prompt_name
    
    if not prompt_dir.is_dir():
        raise FileNotFoundError(f"Prompt directory '{prompt_dir}' does not exist.")
    
    if version == "latest":
        prompt_files = sorted(
            prompt_dir.glob("*.txt"),
            key=lambda f: _version_key(f.stem),
            reverse=True,
        )
        if not prompt_files:
            raise FileNotFoundError(f"No prompt files found in '{prompt_dir}'.")
        prompt_file = prompt_files[0]
    else:
        prompt_file = prompt_dir / f"{version}.txt"
        if not prompt_file.is_file():
            raise FileNotFoundError(
                f"Prompt version '{version}' not found at '{prompt_file}'."
            )

    return prompt_file.read_text(encoding="utf-8").strip()
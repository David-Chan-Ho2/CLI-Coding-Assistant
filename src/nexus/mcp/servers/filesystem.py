"""Filesystem MCP server for NEXUS."""

import pathlib
from fastmcp import FastMCP

filesystem_server = FastMCP("NEXUS Filesystem")


@filesystem_server.tool()
def read_file(path: str) -> str:
    """Read the contents of a file at the given path."""
    try:
        file_path = pathlib.Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Path is not a file: {path}"
        return file_path.read_text(encoding="utf-8")
    except PermissionError:
        return f"Error: Permission denied reading: {path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@filesystem_server.tool()
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    try:
        file_path = pathlib.Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote {len(content)} characters to {path}"
    except PermissionError:
        return f"Error: Permission denied writing to: {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@filesystem_server.tool()
def list_directory(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        dir_path = pathlib.Path(path)
        if not dir_path.exists():
            return f"Error: Directory not found: {path}"
        if not dir_path.is_dir():
            return f"Error: Path is not a directory: {path}"

        entries = sorted(dir_path.iterdir(), key=lambda e: (e.is_file(), e.name))
        if not entries:
            return f"Directory is empty: {path}"

        lines = []
        for entry in entries:
            if entry.is_dir():
                lines.append(f"[DIR]  {entry.name}/")
            else:
                lines.append(f"[FILE] {entry.name} ({entry.stat().st_size} bytes)")

        return f"Contents of {path}:\n" + "\n".join(lines)
    except PermissionError:
        return f"Error: Permission denied listing: {path}"
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@filesystem_server.tool()
def search_files(pattern: str, directory: str = ".", recursive: bool = True) -> str:
    """Search for files matching a glob pattern in a directory."""
    try:
        dir_path = pathlib.Path(directory)
        if not dir_path.exists():
            return f"Error: Directory not found: {directory}"

        matches = list(dir_path.rglob(pattern)) if recursive else list(dir_path.glob(pattern))

        if not matches:
            return f"No files found matching '{pattern}' in {directory}"

        lines = [str(m) for m in sorted(matches)]
        return f"Found {len(matches)} file(s) matching '{pattern}':\n" + "\n".join(lines)
    except Exception as e:
        return f"Error searching files: {str(e)}"


@filesystem_server.tool()
def create_directory(path: str) -> str:
    """Create a directory and any missing parent directories."""
    try:
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)
        return f"Successfully created directory: {path}"
    except PermissionError:
        return f"Error: Permission denied creating: {path}"
    except Exception as e:
        return f"Error creating directory: {str(e)}"


@filesystem_server.tool()
def delete_file(path: str) -> str:
    """Delete a file at the given path."""
    try:
        file_path = pathlib.Path(path)
        if not file_path.exists():
            return f"Error: File not found: {path}"
        if not file_path.is_file():
            return f"Error: Path is not a file (use delete_directory for dirs): {path}"
        file_path.unlink()
        return f"Successfully deleted: {path}"
    except PermissionError:
        return f"Error: Permission denied deleting: {path}"
    except Exception as e:
        return f"Error deleting file: {str(e)}"

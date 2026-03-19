"""Unit tests for the filesystem MCP server tools."""

import pytest
from fastmcp import Client

from nexus.mcp.servers.filesystem import filesystem_server


@pytest.fixture
def test_file(tmp_path):
    """Create a temp file with known content."""
    f = tmp_path / "hello.txt"
    f.write_text("Hello, NEXUS!")
    return f


@pytest.mark.asyncio
async def test_read_file_success(test_file):
    """Read an existing file returns its content."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("read_file", {"path": str(test_file)})
        assert "Hello, NEXUS!" in result.content[0].text


@pytest.mark.asyncio
async def test_read_file_not_found():
    """Reading a missing file returns an error message."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("read_file", {"path": "/does/not/exist.txt"})
        assert "Error" in result.content[0].text


@pytest.mark.asyncio
async def test_write_file_creates_file(tmp_path):
    """Writing a file creates it with the correct content."""
    target = tmp_path / "output.txt"

    async with Client(filesystem_server) as client:
        result = await client.call_tool("write_file", {
            "path": str(target),
            "content": "Written by NEXUS",
        })
        assert "Successfully" in result.content[0].text

    assert target.read_text() == "Written by NEXUS"


@pytest.mark.asyncio
async def test_write_file_creates_nested_dirs(tmp_path):
    """Writing a file auto-creates any missing parent directories."""
    target = tmp_path / "nested" / "dirs" / "file.txt"

    async with Client(filesystem_server) as client:
        result = await client.call_tool("write_file", {
            "path": str(target),
            "content": "nested",
        })
        assert "Successfully" in result.content[0].text

    assert target.read_text() == "nested"


@pytest.mark.asyncio
async def test_write_file_overwrites_existing(tmp_path):
    """Writing to an existing file overwrites its content."""
    target = tmp_path / "existing.txt"
    target.write_text("old content")

    async with Client(filesystem_server) as client:
        await client.call_tool("write_file", {
            "path": str(target),
            "content": "new content",
        })

    assert target.read_text() == "new content"


@pytest.mark.asyncio
async def test_list_directory(tmp_path):
    """Listing a directory shows files and subdirectories."""
    (tmp_path / "a.py").write_text("")
    (tmp_path / "b.py").write_text("")
    (tmp_path / "subdir").mkdir()

    async with Client(filesystem_server) as client:
        result = await client.call_tool("list_directory", {"path": str(tmp_path)})
        output = result.content[0].text

    assert "a.py" in output
    assert "b.py" in output
    assert "subdir" in output


@pytest.mark.asyncio
async def test_list_directory_not_found():
    """Listing a missing directory returns an error message."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("list_directory", {"path": "/no/such/dir"})
        assert "Error" in result.content[0].text


@pytest.mark.asyncio
async def test_list_empty_directory(tmp_path):
    """Listing an empty directory reports it as empty."""
    empty = tmp_path / "empty"
    empty.mkdir()

    async with Client(filesystem_server) as client:
        result = await client.call_tool("list_directory", {"path": str(empty)})
        assert "empty" in result.content[0].text.lower()


@pytest.mark.asyncio
async def test_search_files_finds_matches(tmp_path):
    """Search returns only files matching the pattern."""
    (tmp_path / "foo.py").write_text("")
    (tmp_path / "bar.py").write_text("")
    (tmp_path / "baz.txt").write_text("")

    async with Client(filesystem_server) as client:
        result = await client.call_tool("search_files", {
            "pattern": "*.py",
            "directory": str(tmp_path),
        })
        output = result.content[0].text

    assert "foo.py" in output
    assert "bar.py" in output
    assert "baz.txt" not in output


@pytest.mark.asyncio
async def test_search_files_recursive(tmp_path):
    """Search recurses into subdirectories by default."""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.py").write_text("")

    async with Client(filesystem_server) as client:
        result = await client.call_tool("search_files", {
            "pattern": "*.py",
            "directory": str(tmp_path),
        })
        assert "deep.py" in result.content[0].text


@pytest.mark.asyncio
async def test_search_files_no_matches(tmp_path):
    """Search with no matches returns a descriptive message."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("search_files", {
            "pattern": "*.xyz",
            "directory": str(tmp_path),
        })
        assert "No files found" in result.content[0].text


@pytest.mark.asyncio
async def test_create_directory(tmp_path):
    """Creating a directory (including nested) succeeds."""
    new_dir = tmp_path / "new" / "nested"

    async with Client(filesystem_server) as client:
        result = await client.call_tool("create_directory", {"path": str(new_dir)})
        assert "Successfully" in result.content[0].text

    assert new_dir.is_dir()


@pytest.mark.asyncio
async def test_create_directory_already_exists(tmp_path):
    """Creating a directory that already exists does not error."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("create_directory", {"path": str(tmp_path)})
        assert "Successfully" in result.content[0].text


@pytest.mark.asyncio
async def test_delete_file_success(tmp_path):
    """Deleting an existing file removes it."""
    target = tmp_path / "delete_me.txt"
    target.write_text("temporary")

    async with Client(filesystem_server) as client:
        result = await client.call_tool("delete_file", {"path": str(target)})
        assert "Successfully" in result.content[0].text

    assert not target.exists()


@pytest.mark.asyncio
async def test_delete_nonexistent_file():
    """Deleting a missing file returns an error message."""
    async with Client(filesystem_server) as client:
        result = await client.call_tool("delete_file", {"path": "/no/such/file.txt"})
        assert "Error" in result.content[0].text

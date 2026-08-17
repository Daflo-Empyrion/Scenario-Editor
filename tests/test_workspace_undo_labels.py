from core.workspace_undo import WorkspaceUndoStack, FileStateUndo


def test_all_labels_empty_stack():
    stack = WorkspaceUndoStack()
    assert stack.all_labels() == []


def test_all_labels_returns_oldest_to_newest():
    stack = WorkspaceUndoStack()
    stack.push(FileStateUndo(path="/tmp/a.ecf", prior_bytes=b"", label="Premiere action"))
    stack.push(FileStateUndo(path="/tmp/b.ecf", prior_bytes=b"", label="Deuxieme action"))
    stack.push(FileStateUndo(path="/tmp/c.ecf", prior_bytes=b"", label="Troisieme action"))

    labels = stack.all_labels()
    assert labels == ["Premiere action", "Deuxieme action", "Troisieme action"]


def test_all_labels_respects_max_depth():
    stack = WorkspaceUndoStack(max_depth=3)
    for i in range(5):
        stack.push(FileStateUndo(path=f"/tmp/{i}.ecf", prior_bytes=b"", label=f"Action {i}"))
    labels = stack.all_labels()
    assert len(labels) == 3
    assert labels == ["Action 2", "Action 3", "Action 4"]

# Connect your book to Codex

You only need to do this once for a book workspace. Afterward, open that folder in VS Code and ask manuscript questions normally. You do not need to open scholium’s application folder.

## Your existing book

Run this in a terminal:

```sh
scholium setup /Users/csaborio/code/scholium-tests --codex
```

It keeps your existing book configuration and creates the instructions Codex needs. If AGENTS.md already exists, it is preserved; see “Existing instructions” below.

In VS Code, choose **File → Open Folder…** and select:

```text
/Users/csaborio/code/scholium-tests
```

Start a new conversation in the Codex panel and ask:

> Check my manuscript and tell me which chapters are available.

Then ask your scholarly question:

> How does my treatment of Goethe differ across chapters?

## What the setup does

Setup puts a file named **AGENTS.md** in the book folder. Codex reads that file when it starts work there. It identifies scholium, your book configuration, how to find passages and notes, how to cite them, and how to save summaries or review decisions.

Running scholium in another terminal does not itself connect Codex. The instruction file supplies the connection. Codex does not automatically remember previous chats or know the manuscript; it searches and reads evidence for your question.

Your Word files stay where they are. In your current arrangement, scholium-tests is the book workspace, scholium-data holds the Word chapters, and scholium holds the application. You do not need to move those folders.

## Existing instructions or a conversation already open

Setup never replaces an existing AGENTS.md. If you already copied the earlier instructions, manuscript questions should still work. To use the complete current instructions in an existing chat, paste:

> Read /Users/csaborio/code/scholium/docs/codex/AGENTS.md and follow it when working with my manuscript. Check which chapters are current before answering.

To update an existing workspace file, ask Codex to merge the manuscript instructions into that file while keeping any other rules. Start a new conversation after updating it. If you work in a different VS Code folder, place the manuscript AGENTS.md there instead; it can still point to the same book configuration.

If Codex reports a file-access restriction, give it access to the specific book or source folder it identifies. The instruction file identifies files; it does not override access permissions.

## After setup

Use the [academic user guide](USER_GUIDE.md) for questions and everyday work. After editing in Word, ask Codex to refresh the book and use your latest saved chapters. If you already keep scholium watch running in another terminal, it can continue updating there.

For a new book or computer, installation, source-folder selection and recovery are covered in [Installation and maintenance](OPERATIONS.md).

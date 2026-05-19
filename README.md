# GitGudHub

A web based version control platform inspired by GitHub, built with Python and Flask.

GitGudHub allows users to create repositories, manage branches, upload commits, compare file changes, merge branches, and visualize commit history through an interactive interface.

This project was originally developed as a final high school software engineering project in 2021.

---

# Overview

GitGudHub recreates core concepts of distributed version control systems and repository hosting platforms.

The system supports:

- User authentication
- Repository management
- Branch creation
- Commit history tracking
- File version comparison
- Merge operations
- Commit graph visualization
- Archive based commit storage
- Permission and ownership handling
- SQL backed persistent storage

The project combines backend development, database management, HTTP request handling, filesystem operations, and frontend rendering into a complete web application.

---

# Features

## User System

- User registration and login
- Session based authentication
- Admin and regular user permissions
- Persistent login handling using Flask sessions

## Repository Management

- Create and manage repositories
- Repository ownership system
- Collaborator access handling
- Repository browsing interface

## Branching System

- Create new branches from existing commits
- Separate development flows
- Branch ownership tracking
- Suggestion based workflow for non owners

## Commit System

- Upload commits as ZIP archives
- Add commit messages and descriptions
- Track complete commit history
- Store multiple repository versions efficiently

## Diff and History Visualization

- Compare commits
- Show added, removed, and modified files
- View file history across commits
- Render commit trees visually

## Merge System

- Merge branches through an interactive UI
- Preview merge changes before confirmation
- Visualize selected commits during merge

## Admin Tools

- Browse user database data
- Visualize all repositories
- View internal database content as JSON

---

# Screenshots and Interface

The application includes:

- Login and registration pages
- User profile dashboard
- Repository selector
- Commit graph visualization
- File diff viewer
- Merge popup interface
- File history viewer
- Admin management pages

The UI was built with HTML, CSS, Flask templates, and JavaScript.

---

# Tech Stack

## Backend

- Python 3.x
- Flask
- SQLite3

## Frontend

- HTML
- CSS
- JavaScript
- Jinja2 Templates

## Libraries and Modules

- os
- os.path
- shutil
- sqlite3
- json
- re
- time
- numpy
- cv2

---

# Architecture

## HTTP and Flask

The project runs on HTTP using Flask.

Static files such as images, CSS, and HTML templates are handled through GET requests.

User input such as login credentials and commit information is sent through POST requests.

Flask features used in the project include:

- session
- flash
- redirect
- url_for
- template rendering
- error handling

---

# Database Design

The system uses a relational SQLite database.

Core entities include:

- Users
- Repositories
- Branches
- Commits
- Messages
- Ownership relations

The application also mirrors database data through object oriented Python classes.

Example structure:

- Repo class
  - Branch objects
    - Commit objects

Each class contains helper methods for interacting with the database.

---

# File Storage System

## Commit Archives

All commits are stored as ZIP archives.

Benefits:

- Reduced storage usage
- Easier downloads
- Faster commit packaging
- Simplified file transport

## Temporary Extraction

When calculating diffs or scanning commit contents, the application extracts archives into temporary folders.

Folder naming format:

```text
purpose_id_timestamp
```

This prevents collisions and overlapping scans.

---

# Algorithms and Internal Logic

## Commit Delta Calculation

To compare commits:

1. Both commit archives are extracted.
2. Files are scanned recursively.
3. Directory trees are converted into dictionaries.
4. Files are compared using loops and path matching.
5. Added, removed, and modified files are returned.

## File History Tracking

When a commit is selected:

1. The application traverses commit ancestry.
2. Every previous commit is scanned.
3. File changes are tracked over time.
4. A history list is generated for every file.

## Graph Reloading

To force browsers to reload updated commit graph images:

1. The existing image is copied.
2. The old file is deleted.
3. The image is rewritten with a timestamped filename.

This bypasses browser cache issues.

## Commit File Listing

The application uses `os.walk()` to recursively collect file names from commit directories.

---

# Ownership and Collaboration

Every repository, branch, and commit contains ownership metadata.

If a user attempts to modify a branch they do not own:

- Their action becomes a suggestion
- The branch owner receives a message
- The owner can approve or reject the change

This simulates pull request style workflows.

---

# Project Structure

```text
project/
│
├── app.py
├── templates/
├── static/
├── database/
├── repositories/
├── temp_zip/
├── classes/
├── utils/
└── archives/
```

---

# Installation

## Requirements

- Python 3.x
- pip

## Clone the Repository

```bash
git clone https://github.com/IMakeBotsForYou/github_project.git
cd github_project
```

## Install Dependencies

```bash
pip install flask numpy opencv-python
```

## Run the Application

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

---

# Example Workflow

## Creating a Repository

1. Register or log in.
2. Create a new repository.
3. Upload the initial commit.

## Creating a Branch

1. Select a commit.
2. Press the Branch button.
3. Create a new branch from the selected commit.

## Uploading a Commit

1. Select a repository.
2. Choose a branch.
3. Upload a ZIP archive.
4. Add a commit message.
5. Submit the commit.

## Merging Branches

1. Open the merge interface.
2. Select target commits.
3. Preview changes.
4. Confirm the merge.

---

# Educational Goals

This project focused on:

- Understanding version control systems
- Working with SQL databases
- Building web applications with Flask
- Designing object oriented systems
- Handling file operations and archives
- Managing HTTP requests and sessions
- Implementing commit comparison logic
- Creating interactive web interfaces

---

# Limitations

- File comparison is basic
- No hashing based storage
- No real Git integration
- SQLite only
- Local deployment focused
- Simplified merge logic

The original project intentionally avoided hashing complexity for simplicity and development speed.

---

# Future Improvements

Potential future upgrades:

- Git compatible storage
- Real diff engine
- Pull request system
- WebSocket live updates
- Docker deployment
- User permissions system
- Better merge conflict handling
- REST API
- Cloud storage
- Repository search
- CI/CD integration

---

# License

This project was created for educational purposes.

---

# Author

Dan Lvov

Final Software Engineering Project
2021

---

# Acknowledgements

Inspired by:

- GitHub
- Git version control workflows
- Flask web framework
- SQLite relational databases


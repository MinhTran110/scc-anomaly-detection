# Git Workflow for SCC Anomaly Detection



This document describes the recommended Git workflow for contributing to the SCC Anomaly Detection project.



## 1. Create a Feature Branch



Always create a separate branch for a new feature, bug fix, or documentation update.



```bash

git switch main

git pull origin main

git switch -c feature/your-feature-name

```



## 2. Make Changes and Review Them



After modifying files, inspect the changes before committing:



```bash

git status

git diff

```



Avoid committing generated runtime data, temporary files, credentials, or local environment configurations.



## 3. Commit Changes



Stage only the files related to your contribution:



```bash

git add docs/GIT\_WORKFLOW.md

git commit -m "docs: add Git workflow guide"

```



Use clear commit messages that describe the purpose of each change.



## 4. Push the Branch



Push your branch to GitHub:



```bash

git push -u origin feature/your-feature-name

```



## 5. Open a Pull Request



Create a Pull Request from your feature branch into `main`.



The Pull Request should include:

- A clear title and description.

- The purpose of the change.

- Relevant implementation details.

- Testing or verification performed.



## 6. Merge the Pull Request



After reviewing the changes and confirming they are ready, merge the Pull Request into `main`.



Keep the repository clean by deleting merged feature branches when appropriate.


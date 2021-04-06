import sqlite3


def st2int(array):
    return [int(x) for x in array]


def int2st(array):
    return [str(x) for x in array]


def reformat(vars):
    """
    :param vars: Variables seperated by |
    :return: formated string (var1, var2, var3..) for SQL purposes
    """
    st = "("
    vars = list(vars)
    for var in vars:
        if isinstance(var, int):
            st += f'{var}, '
        elif isinstance(var, list):
            st += "{" + ", ".join(var) + "}"
        else:
            st += f'"{var}", '
    return st[:-2] + ")"


class commit:
    def __init__(self, db, name, comment, parent, creator, previous_commit=1, id=1, create=True, next_commit=-1):
        # Declare variables
        self.db = db
        self.name = name
        self.comment = comment
        self.parent = parent
        self.creator = creator
        self.previous = int(previous_commit)
        self.next_commit = next_commit
        self.depth = self.parent.depth
        self.repo = self.parent.get_repo()
        self.changed_files = []
        # Adding to database
        if create:
            self.id = len(db.get("commits", "id")) + 1
            db.add("commits (commit_name, comment, branch, repo, creator, previous_commit, next_commit, depth)",
                   reformat((name, comment, parent.get_id(), self.repo, creator, self.previous, -1, self.depth)))
        else:
            x = f'comment = "{self.comment}" ' \
                f'AND branch = "{self.parent.get_id()}" ' \
                f'AND commit_name = "{self.name}" ' \
                f'AND creator = "{creator}"'
            x = db.get('commits', 'id, next_commit', condition=x, first=False)[0]
            if x:
                self.id = x[0]
                self.next_commit = int(x[1])
        # add sync (?) function

    def to_json(self):
        return {
            "type": "commit",
            "id": self.id,
            "name": self.name,
            "comment": self.comment,
            "branch": self.parent.get_id(),
            "repo": self.parent.get_repo(),
            "creator": self.creator,
            "next_commit": self.next_commit,
            "previous_commit": self.previous,
            "depth": self.depth
        }

    def get_id(self):
        return self.id

    def get_comment(self):
        return self.comment

    def get_parent(self):
        return self.parent

    def get_repo(self):
        return self.repo

    def get_name(self):
        return self.name

    def get_previous(self):
        return self.previous

    def set_next(self, id):
        self.next_commit = id
        self.db.edit("commits", "next_commit", id, condition=f'id="{self.id}"')


class branch:
    def __init__(self, db, name, repo, create=True, id=1, files=None, depth=-1):
        # Declare variables
        if files is None:
            files = []
        self.db = db
        self.repo = repo
        self.name = name
        self.commits = []
        # self.depth = len(self.db.get_repos())
        # Adding to database
        if create:
            db.add("branches (name, repo, commits)", reformat((name, repo, " ")))
            self.id = len(db.get("branches", "id"))
        else:
            self.id = id
        if depth == -1:
            self.depth = len([x for x in db.get("branches", "id", f'repo={repo}') if x < self.id])
        else:
            self.depth = depth
        for numba, x, comment, creator, previous_commit in \
                db.get("commits", "id, commit_name, comment, creator, previous_commit",
                       condition=f'branch="{self.id}"', first=False):
            self.commits.append(commit(db, x, comment, self, creator, previous_commit, id=numba, create=False))
        if self.commits:
            self.head = self.commits[-1]
        else:
            self.head = 0
        # add sync (?) function

    def to_json(self):
        return {
            "type": "branch",
            "id": self.id,
            "name": self.name,
            "repo": self.repo,
            "commits": [x.to_json() for x in self.commits],
            "depth": self.depth
        }

    def set_depth(self, int):
        self.depth = int

    def get_id(self):
        return self.id

    def get_repo(self):
        return self.repo

    def get_commits(self):
        return self.commits

    def get_files(self):
        return self.files

    def set_name(self, name):
        self.name = name

    def get_name(self):
        return self.name

    def create_commit(self, name, comment, creator, previous=-1, first=False, next_commitx=-1):
        if previous == -1:
            # the user didn't specify what commit this extends,
            # so it will stay -1 if it's the first commit,
            # or extend the last commit to this branch.
            previous = -1 if (len(self.commits) == 0 or first) else self.commits[-1].get_id()
        self.commits.append(
            commit(self.db, name, comment, self, creator, previous, next_commit=next_commitx))

        # we also need to say in that commit that it's next
        # commit is the one we've added.
        # -1 is now the new commit.
        if len(self.commits) > 1:
            self.commits[-2].set_next(self.commits[-1].get_id())
            self.head = self.commits[-1]
        self.db.edit("branches", "commits", ", ".join(int2st([comm.get_id() for comm in self.commits])),
                     condition=f'id={self.id}')

    def get_commit(self, id):
        for c in self.commits:
            if str(c.get_id()) == str(id) or c.get_name() == str(id):
                return c
        raise IndexError(f'Could not find {id.get_name()} in {self.name}')

    def revert_to_commit(self, index):
        self.head = self.commits[index].get_id()
        self.commits = self.commits[:index + 1]

    def delete_commit(self, id):
        try:
            self.commits.remove(self.get_commit(id))
        except ValueError:
            print(f"ID {id} not found in branches.")
        self.db.remove("commits", condition=f'id="{id}"')
        self.head = self.commits[-1]


class repository:
    def __init__(self, db, name, owners, creator, branches=None, create=True, id=1):
        # Declare variables

        self.name = name
        if isinstance(owners, str):
            self.owners = owners.split(", ")
        else:
            self.owners = owners
        if creator not in self.owners:
            self.owners.append(creator)
        self.creator = creator
        if isinstance(branches, str):
            self.branches = branches.split(", ")
        else:
            self.branches = branches
        if branches is None:
            self.branches = []
        self.db = db
        self.current_depths = []

        # Adding to database
        if create:
            db.add("repos (name, branches)", reformat((name, "")))
            self.id = db.get("repos", "id")[-1]
            db.edit('repos', 'owners', ", ".join(self.owners), condition=f'id="{self.id}"')
            # self, db, name, repo, create=True, id=1, files=None
            self.branches.append(branch(db, "Main", self.id))
        else:
            self.id = id
            db.edit('repos', 'owners', ", ".join(self.owners), condition=f'id="{self.id}"')
            for name, id_bruh in \
                    self.db.get("branches", "name, id", condition=f'repo="{self.id}"', first=False):
                self.branches.append(branch(self.db, name, self.id, create=False, id=id_bruh))
        db.sync_ownership()
        self.db.sync_branches()
        # add sync (?) function

    def to_json(self):
        return {
            "type": "repo",
            "id": self.id,
            "name": self.name,
            "branches": [x.to_json() for x in self.branches],
            "owners": self.owners
        }

    def fork(self, name, forker, new_name=None, fork_from_commit=None, comment=""):
        #  db, name, repo, create=True, id=1, files=[]
        to_copy = self.get_branch(name)
        if not fork_from_commit:
            fork_from_commit = to_copy.head.get_id()
        if new_name:
            names = [b.get_name() for b in self.branches]
            if new_name in names:
                raise NameError(
                    f"There's already a branch called {name} in repo {self.name}, please pick a different name")
        else:
            new_name = name + "_fork"
        self.branches.append(branch(self.db, new_name, self.id, files=to_copy.get_files()))
        # name, comment, creator, previous = -1, first = False, next_commitx = -1)
        self.branches[-1].create_commit(f"Forked from {to_copy.get_name()}", "Forked.", forker,
                                        previous=fork_from_commit)

    def merge(self, merge_me, merge_into, merger, commit_name="Merged", comment="No comment provided."):
        merge_me = self.get_branch(merge_me)
        merge_into = self.get_branch(merge_into)
        # self.current_depths.remove(merge_me.depth)
        prev_h = merge_into.head
        merge_into.create_commit(commit_name, comment, merger, merge_me.head.get_id())
        merge_me.head.set_next(merge_into.head.get_id())
        prev_h.set_next(merge_into.head.get_id())

    def edit_owners(self, new_owners):
        self.owners = ", ".join(list(set(new_owners)))
        self.db.edit("repos", "owners", self.owners, condition=f'id={self.id}')
        self.db.sync_ownership()

    def add_owners(self, new_owners):
        self.owners.append(new_owners)
        self.edit_owners(self.owners)
        self.db.sync_ownership()

    def remove_owners(self, new_owners):
        self.owners.remove(new_owners)
        self.edit_owners(self.owners)
        self.db.sync_ownership()

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name

    def get_owners(self):
        return self.owners

    def create_branch(self, name):
        names = [b.get_name() for b in self.branches]
        if name in names:
            raise NameError(f"There's already a branch called {name} in repo {self.name}, please pick a different name")
        self.branches.append(branch(self.db, name, self.id, create=True))
        # self.current_depths.append(self.get_lowest_empty())
        # self.branches[-1].set_depth(self.get_lowest_empty())
        self.db.sync_branches()

    def get_branch(self, name):
        for b in self.branches:
            if b.get_name() == name or str(b.get_id()) == str(name):
                return b
        raise IndexError(f"Couldn't find branch {name} in repo {self.name}")

    def delete_branch(self, name):
        try:
            x = self.get_branch(name)
            self.db.remove("branches", condition=f'id="{x.get_id()}"')
            self.branches.remove(x)
        except ValueError:
            print(f"Name {name} not found in branches.")
        self.db.sync_branches()

    def get_branches(self):
        return self.branches


class Database:
    def __init__(self, path):
        # if path.find('/') != -1:
        # this takes the entire path, up to the file name
        # not including, and creates the repository
        # folder_path = re.sub(r"(.+)(/.+)", r"\1", path).replace("/", "\\")
        # if not os.path.exists(folder_path):
        #     os.makedirs(folder_path)
        self.path = path.split(".")[0] + '.db'
        self.data = sqlite3.connect(self.path, check_same_thread=False)
        self.cursor = self.data.cursor()
        self.repos = []
        self.purge_deleted_commit_ids()
        for id, name, branches, owners, creator in self.get("repos", "*", first=False):
            self.repos.append(
                repository(self, name, owners, creator,
                           [],
                           create=False,
                           id=id))
        self.remove("messages")
        # branch(self, name=name, repo=repo, create=False,files=files)
        #                         for name, repo, files in
        #                         self.get("branches JOIN repos ON repos.branches LIKE branches.id",
        #                                  "branches.name, branches.repo, branches.files", first=False)
        self.add("messages",
                 reformat(("1", "Urgent message", "You got bamboozled lolololol", "Eran", "Guy", "normal", "/ignore")))

        self.add("messages",
                 reformat(("2", "Merge request", "can i merge pain into main plz", "Eran", "Guy", "question", "/merge*8*4")))

        self.add("messages",
                 reformat(("3", "Yet another request", "lets just merge it all. whats the worst that can happen?", "Eran", "Guy", "question", "/merge*7*9")))

        self.add("messages",
                 reformat(("4", "Actually urgent!", "Fell for it again", "Eran", "Guy", "normal", "/ignore")))

        self.fix_seq()
        self.sync_commits()
        self.sync_branches()
        self.sync_ownership()

    def get_all_names(self):
        return self.get("users", "name")

    def get_users(self, colum=None):
        return self.get("users", colum if colum else "*", first=colum)

    def get_commits_info(self, repo):
        if str(repo).isnumeric():
            return self.get('commits', 'id, commit_name, comment, branch, next_commit, previous_commit, depth',
                            condition=f'repo={repo}', first=False)
        else:
            repo_id = self.get("repos", "id", f'name="{repo}"')[0]
            return self.get(f'commits', 'id, commit_name, comment, branch, '
                                        'next_commit, '
                                        'previous_commit, depth', condition=f'repo="{repo_id}"', first=False)

    def fix_seq(self):
        b = self.get("branches", "id")
        self.edit("sqlite_sequence", "seq", len(b), 'name="branches"')
        r = self.get("repos", "id")
        self.edit("sqlite_sequence", "seq", len(r), 'name="repos"')
        c = self.get("commits", "id")
        self.edit("sqlite_sequence", "seq", len(c), 'name="commits"')
        m = self.get("messages", "id")
        self.edit("sqlite_sequence", "seq", len(m), 'name="messages"')
        # b = self.get("branches", "id")
        # self.edit("sqlite_sequence", "seq", 0 if not b else b[-1], 'name="branches"')
        # r = self.get("branches", "id")
        # self.edit("sqlite_sequence", "seq", 0 if not r else r[-1], 'name="repos"')
        # c = self.get("commits", "id")
        # self.edit("sqlite_sequence", "seq", 0 if not c else c[-1], 'name="commits"')

    # self, db, name, owners, create=True, id=1

    def get_repos(self):
        return self.repos

    def get_messages(self):
        mes = self.get('messages', '*', first=False)
        ret = {"status": "empty", "messages": {}}
        for message in mes:
            xx, title, content, sender, receiver, m_type, action = message
            ret["status"] = "200"
            if receiver in ret['messages']:
                ret["messages"][receiver].append(
                    {"id": xx,
                     "title": title,
                     "content": content,
                     "sender": sender,
                     "type": m_type,
                     "action": action
                     })
            else:
                ret["messages"][receiver] = \
                    [{"id": xx,
                      "title": title,
                      "content": content,
                      "sender": sender,
                      "type": m_type,
                     "action": action
                      }]
        return ret

    def to_json(self):
        return {
            "repos": [x.to_json() for x in self.repos],
            "messages": self.get_messages()
        }

    def create_repository(self, name, owners, creator):
        try:
            self.repos.append(repository(self, name, owners.split(", "), creator, None, create=True))

        except:
            self.repos.append(repository(self, name, owners, creator, " ", create=True))

    def delete_repository(self, id):
        for rep in self.repos:
            if str(rep.get_id()) == str(id):
                self.remove("branches", condition=f'repo={id}')
                self.remove("commits", condition=f'repo={id}')
                self.remove("repos", condition=f'id="{id}"')
                self.repos.remove(rep)
        self.sync_ownership()

    def execute(self, line, fetch=None):
        """
        :param line: SQL command
        :param fetch: Number to of results to return
        :return: The results
        """
        self.cursor.execute(line)
        if not fetch or fetch == -1:
            ret = self.cursor.fetchall()
            self.data.commit()
            return ret
        else:
            ret = self.cursor.fetchmany(fetch)
            self.data.commit()
            return ret

    def add(self, table, values):
        # try:
        self.data.execute(F"INSERT INTO {table} VALUES {values}")
        # except Exception as e:
        #     print(1, e)
        self.data.commit()

    def remove(self, table, condition=None):
        self.data.execute(f'DELETE FROM {table} WHERE {"1=1" if not condition else condition}')
        self.fix_seq()

    def edit(self, table, column, newvalue, condition=None):
        s = f'UPDATE {table} SET {column} = "{newvalue}"'
        s += f" WHERE {condition}" if condition else " WHERE 1=1"
        self.execute(s)

    def add_user(self, name, password, libraries=None):
        if libraries is None:
            libraries = [-1]
        if isinstance(libraries, list):
            self.add("users", reformat((name, password, ', '.join(int2st(libraries)))))
        else:
            self.add("users", reformat((name, password, libraries)))
        self.sync_ownership()

    def get(self, table, column, condition=None, limit=None, first=True):
        """
        :param table: database table
        :param column: What column?
        :param condition: condition of search
        :param limit: Limit the search to X results
        :param first: Return first of every result
        :return: The results
        """
        s = f"SELECT {column} FROM {table}"
        if condition: s += f" WHERE {condition}"
        if limit: s += f" LIMIT {limit}"
        return [x[0] if first else x for x in self.execute(s)]

    def remove_user(self, name, password):
        try:
            if password == self.execute(f'SELECT password FROM users WHERE name="{name}"', 1)[0][0]:
                self.data.execute(f'DELETE FROM users WHERE name="{name}"')
            else:
                print("Wrong password, you can't do that.")
        except IndexError:
            print(f"User {name} isn't registered!")

    def sync_ownership(self):
        # override user settings by what's saved in the repo data
        clients = [[x, y] for x, y in self.get("users", "name, repos", first=False)]
        all_repos = [[x, y] for x, y in self.get("repos", "id, owners", first=False)]
        for name, repos in clients:
            true_repos = []
            for id, owners in all_repos:
                if name in owners:
                    true_repos.append(str(id))
            self.edit("users", "repos", ", ".join(true_repos), f'name="{name}"')

    def sync_commits(self):
        # override user settings by what's saved in the repo data
        all_commits = [[x, y] for x, y in self.get("commits", "id, branch", first=False)]
        conn = {}
        for commit, branch in all_commits:
            if branch not in conn:
                conn[branch] = [commit]
            else:
                conn[branch].append(commit)
        # print(conn)
        for b in conn:
            self.edit('branches', 'commits', ", ".join(int2st(conn[b])), condition=f'id="{b}"')

    def sync_branches(self):
        # override user settings by what's saved in the repo data
        all_repos = [[x, y] for x, y in self.get("repos", "id, branches", first=False)]
        for id, branches in all_repos:
            true_branches = self.get("branches", "id", condition=f'repo="{id}"', first=True)
            self.edit("repos", "branches", ", ".join(int2st(true_branches)), f'id="{id}"')

    def get_repo(self, val, all=False):
        if all:
            return self.repos
        x = [rep for rep in self.repos if str(rep.get_id()) == str(val) or rep.get_name() == val]
        if x:
            return x[0]
        raise IndexError(f"Couldn't find {val}")

    def grant_ownership(self, user, repos_to_grant):
        for rep in repos_to_grant.split(", "):
            try:
                repo = self.get("repos", "owners", condition=f'id="{rep}"')[0]
                repo.append(user)
                self.get_repo(rep).edit_owners(repo)
            except IndexError:
                print("Couldn't do", rep)

    def revoke_ownership(self, user, repos_to_revoke):
        for rep in repos_to_revoke.split(', '):
            try:
                current_owned_repos = self.get("users", "repos", condition=f'name="{user}"')
                if rep.isnumeric():
                    owners_of_repo = self.get("repos", "owners", condition=f'id="{rep}"')
                else:
                    owners_of_repo = self.get("repos", "owners", condition=f'name="{rep}"')

                current_owned_repos.remove(rep)
                owners_of_repo.remove(user)

                self.edit("users", "repos", current_owned_repos, f'name="{user}"')
                if rep.isnumeric():
                    self.edit("repos", "owners", owners_of_repo, f'id="{rep}"')
                else:
                    self.edit("repos", "owners", owners_of_repo, f'name="{rep}"')

            except Exception as e:
                print(f"There was a problem revoking {rep} from {user}\nError: {e}")
                continue

    def purge_deleted_commit_ids(self):
        com = self.get("commits", "id, previous_commit, next_commit", first=False)
        for data in com:
            now = data[0]
            past = data[1]
            future = data[2]
            if len(self.get("commits", "id", f'id={future}')) == 0:
                self.edit("commits", "next_commit", "-1", condition=f'id={now}')

            if len(self.get("commits", "id", f'id={past}')) == 0:
                self.edit("commits", "previous_commit", "-1", condition=f'id={now}')

    def close(self):
        print("Finished")
        self.data.close()

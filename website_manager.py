import json
import re
import time
from os.path import join

from flask import *
from flask_socketio import SocketIO

import database_manager
import graphics_manager
from files_manager import *

app = Flask(__name__)
if __name__ == "__main__":
    # Encrypt all the stuff :)
    app.secret_key = b'_5y2L"\xea2L"F4Q8z\n\xec]\ny2L"F4Q8z\n\xec]]#y2L"F4Q8z\n\xec]/'
    socketio = SocketIO(app)
    # Run app
    database_manager.main()
    # Make it
    db = {"ex": database_manager.my_db}
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), "user_files")


def clear_admin_images():
    # delete all images with the file prefix "admin" to reset admin view
    if session['user'] != db['ex'].admin:
        return
    for fname in os.listdir("static"):
        if fname.startswith("admin_"):
            os.remove(os.path.join("static", fname))


@app.route("/")
def home():
    # If user is logged in
    if "user" in session:
        session['current_repo'] = ""
        session['repo_id'] = 0
        return redirect(url_for("repos"))
    # If they're not logged in, log in.
    session['my_branch'] = True
    return redirect(url_for("login"))


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        # get info from form
        user = request.form['name']
        password = request.form['pass']
        confirm = request.form['confirm']
        all_names = db['ex'].get_all_names()
        if user in all_names:
            flash('This name is already taken.', category='error')
        elif len(user) < 2:
            flash('Name must be longer than 1 character.', category='error')
        elif password != confirm:
            flash('Passwords don\'t match.', category='error')
        elif len(password) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            session['user'] = user
            db['ex'].add_user(user, password, [])
            return redirect(url_for(f"repos"))
        return render_template("register.html")
    else:
        return render_template("register.html")


@app.route("/create_repo", methods=["POST", "GET"])
def create_repo():
    clear_admin_images()
    if "user" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        creator = session['user']
        repo_name = request.form['name']
        actual_names = db['ex'].get_all_names()
        # make list of the names that you invite to have access to the repo
        # we remove invalid names and add the creators name
        owners = list(set([name.strip() for name in request.form['owners'].split(",") if
                           name.strip() != "" and name.strip() in actual_names] + [creator]))
        db['ex'].create_repository(repo_name, owners, creator)
        # change current repo to the created one
        session['current_repo'] = repo_name
        session['repo_id'] = repo_id = db['ex'].get("repos", "id", f'name="{repo_name}"')[0]
        repo_first_commit = db['ex'].get("commits", "id", f'repo={repo_id}')[0]

        new_commit_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                       f"{repo_first_commit}")
        try:
            os.mkdir(new_commit_path)
        except FileExistsError:
            print("Folder is already there")
        else:
            print(f'Made folder for commit {new_commit_path}')

        save_commit_manifest(repo_first_commit, -1)
        graphics_manager.start_draw(session, to_highlight=None,
                                    reload_colors=True, force=True)
        return redirect(url_for("repos"))
    return render_template("create_repo.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        user = request.form['name']
        password = request.form['pass']
        # password = request.form['pass']
        # Is the password correct? Is the user valid?
        # If the user isn't valid, it throws an error.
        try:
            if db['ex'].get("users", "password", f'name="{user}"')[0] != password:
                flash("Either the name, or the password are wrong.")
                return render_template("login.html")
            else:
                session['user'] = user

                # create the instance folder
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                session['is_admin'] = user == db['ex'].admin
                return redirect(f"/repos")
        except:
            flash("Either the name, or the password are wrong.")
            return render_template("login.html")
    else:
        return render_template("login.html")


@app.route('/logout')
def logout():
    clear_admin_images()
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


def commit_to_message(receiver, title, desc, current_id, repo, branch):
    # add commit to queue
    message_title = f'{session["user"]} has suggested {title} in repo {repo} - {branch}'
    message_desc = f"{desc}\n" + \
                   f"Commit delta:\n" + \
                   open(f"./user_files/{current_id}/manifest", 'rb').read().decode()
    message_sender = session['user']
    message_type = "question"
    action = f"/accept*{current_id}"
    db['ex'].send_message(message_title, message_desc, message_sender, receiver, message_type, action)


def make_image_map():
    data = db['ex']
    try:
        branches = data.get_repo(session['repo_id']).get_branches()
        areas = []
        for b in branches:
            areas += [[x.get_id(), b.get_id()] for x in b.get_commits()]
        x = sorted(areas, key=lambda x: x[0])
        # make the coordinate list for the commits of this repo
        # so we can make the image map (clickable areas)
        # in the website.
        for i, b in enumerate(x):
            x[i].append(i)
        session['areas'] = x
    except Exception as e:
        if str(e) not in ["error - 'repo_id'"] and not re.search("error - Couldn't find repo \d+", str(e)):
            flash(f"error - {e}")
            # it just hates me lol :)))))


def reload_image():
    all_static_files = os.listdir(os.getcwd() + "\\static")
    our_file = [x for x in all_static_files if re.search(rf"rendered_{session['user']}_\d+", x)][0]

    new_name = f"rendered_{session['user']}_{str(time.time()).replace('.', '')}.png"
    image_data = open(f'./static/{our_file}', 'rb').read()
    for filename in os.listdir('static/'):
        if filename.startswith(f"rendered_{session['user']}"):  # not to remove other images
            os.remove('static/' + filename)

    with open(f'./static/{new_name}', 'wb') as f:
        f.write(image_data)
    # delete the image, and write it with a different name
    # so your stupid cache doesn't save it
    session['path'] = new_name


def save_commit_manifest(current, previous, merge=False):
    with open(join(app.config['UPLOAD_FOLDER'], f"{current}", "manifest"), "w+b") as f:
        data = generate_commit_diff(current, previous, merge).encode()
        f.write(data)
    return data


def generate_commit_diff(current, previous, merge=False, output_mode=0):
    if str(previous) == "-1":
        current_rp_id = db['ex'].get("commits", "repo", f'id="{current}"')[0]
        current_rp_name = db['ex'].get("repos", "name", f'id="{current_rp_id}"')[0]

        if output_mode == 0:
            # this is the text output mode
            return f'created repo "{current_rp_name}"'
        else:
            return [{"action": "created", "rest": f'repo "{current_rp_name}"'}]

    # get current files
    current_files, unpack_curr = get_commit_files(current)
    previous_files, unpack_prev = get_commit_files(previous)
    print("----------------------------------")
    print(
        f"\n\nBeginning to write manifest. Settings:\nCURR:\t{current}\nPREV:\t{previous}\nMERG:\t{merge}\nMODE:\t{output_mode}\n")
    manifest = "" if output_mode == 0 else []
    # First we check all current directories -> last commit | To check adds / edits
    # then last commit -> current | To check deletes
    for directory in current_files:
        directory = directory.replace("\\", "/")
        no_slash_dir = directory[1:]
        if directory not in previous_files:
            print(f"DIRECTORY {directory} was CREATED")
            # we created a directory, along with all its files.
            if output_mode == 0:
                manifest += f"created {no_slash_dir if directory != '/' else 'root directory'}\n"
            else:
                manifest.append(
                    {"action": "created",
                     "rest": f"{no_slash_dir if directory != '/' else 'root directory'}"}
                )
            for file in [data[0] for data in current_files[directory]]:
                print(f"FILE {file} was ADDED")
                if output_mode == 0:

                    manifest += f"added {no_slash_dir}/{file}\n"
                else:
                    manifest.append(
                        {"action": "added", "rest": f"{no_slash_dir}/{file}"})

        else:
            print(F"FOUND DIR {directory}")
            previous_names = [data[0] for data in previous_files[directory]]
            current_names = [data[0] for data in current_files[directory]]
            for file in current_files[directory]:
                name = file[0]
                data = file[1]
                print(f"FILE {name} was ADDED")
                if name not in previous_names:

                    if output_mode == 0:
                        manifest += f"added {no_slash_dir}/{name}\n"
                    else:
                        manifest.append(
                            {"action": "added", "rest": f"{no_slash_dir}/{name}"})

                else:
                    try:
                        current_bytes = data.read()
                    except:
                        current_bytes = b'Empty'
                    previous_data = [data[1] for data in previous_files[directory] if data[0] == name][0]
                    try:
                        previous_bytes = previous_data.read()
                    except:
                        previous_bytes = b'Empty'
                    if current_bytes != previous_bytes:
                        print(f"FILE {name} was CHANGED")
                        action = "overrode" if merge else "updated"
                        if output_mode == 0:
                            manifest += f"{action} {no_slash_dir}/{name}\n"
                        else:
                            manifest.append(
                                {"action": action, "rest": f"{no_slash_dir}/{name}"})

            if not merge:
                for name in [name for name in previous_names if name not in current_names]:
                    print(f"FILE {name} was DELETED")
                    if output_mode == 0:
                        manifest += f"deleted {no_slash_dir}/{name}\n"
                    else:
                        manifest.append(
                            {"action": "deleted", "rest": f"{no_slash_dir}/{name}"})
        print("\n")
    print("----------------------------------")
    print("\n")
    for path_ in previous_files:
        _ = [data[1].close() for data in previous_files[path_]]
    for path_ in current_files:
        _ = [data[1].close() for data in current_files[path_]]

    print(f"Created manifest for commit #{current}:\n{manifest}")

    shutil.rmtree(unpack_curr)
    shutil.rmtree(unpack_prev)

    return manifest


def read_commit_manifest(commit_id):
    lines = []
    try:
        file = open(join(app.config['UPLOAD_FOLDER'], f"{commit_id}", "manifest"), "rb")
        lines = file.read().decode().split("\n")
    except Exception as e:
        try:
            save_commit_manifest(commit_id, db['ex'].get("commits", "previous_commit", f'id="{commit_id}"')[0])
        except:
            flash("There was an error loading the changes file.")
        else:
            flash("The changes file was reloaded because of an error. ")
            flash("Try reloading the page in a few seconds.")
        print(e)
    data = []
    for line in lines:
        action = line.split(" ")[0]
        if action != "":
            data.append(
                {"action": action,
                 "rest": line[len(action) + 1:]
                 })
    return data


def get_commit_files(commit_id, path=None):
    ret = {}
    unpack_path = None
    if not path:
        path = os.path.join(app.config['UPLOAD_FOLDER'],
                            f"{commit_id}", f"{commit_id}.zip")
        unpack_path = os.path.join("temp_zip", f"reading_{commit_id}_{time.time()}")

        try:
            os.mkdir(unpack_path)
        except Exception as e:
            print(f"Error making temp unpack path for {commit_id}: {e}")
        else:
            print(f"Created temp unpack path for {commit_id}")

        try:
            shutil.unpack_archive(path, unpack_path)
        except shutil.ReadError:
            return ret, unpack_path
        else:
            print(f"Unpacked into {unpack_path}")
        path = unpack_path
    else:
        unpack_path = path

    for root, dirs, files in os.walk(unpack_path):
        for file in files:
            root = root.replace("\\", "/")
            root = root.replace("//", "/")
            # \\\\ -> / could work but i'm lazy
            # append the file name to the list
            directory = root[len(unpack_path):]
            location = os.path.join(root, file)
            if directory == "":
                directory = "/"
            if directory in ret:
                ret[directory].append((file, open(location, 'rb')))
            else:
                ret[directory] = [(file, open(location, 'rb'))]
    return ret, unpack_path


def list_commit_files():
    path = os.path.join("static", "current_files", session['user'])
    filelist = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # append the file name to the list
            if file != "commit_zip.zip":
                filelist.append(os.path.join(root, file)[len(path) + 1:].replace("\\", "/")
                                .replace("//", "/"))
    return filelist


def draw_graph(to_highlight=None, reload_colors=True, erase_var=False, admin_view=False, repo=0):
    try:
        session['image_size'] = graphics_manager.start_draw(session,
                                                            to_highlight,
                                                            reload_colors,
                                                            force=True,
                                                            erase=erase_var,
                                                            admin_view=admin_view,
                                                            repo=repo)
        if not session['image_size']:
            raise ValueError("No size")
    except Exception as e:
        print(e)
        graphics_manager.start_draw(session, erase=True)
        session['image_size'] = [0, 0]
    # request.form['repos'] => current repo id
    try:
        make_image_map()
        # remove cashing
        reload_image()
    except Exception as e:
        if str(e) not in ["error - 'repo_id'"] and not re.search("error - Couldn't find repo \d+", str(e)):
            flash(f"error - {e}")


def parse_action(action):
    commands = ["branch_name_update", "commit", "accept"]
    actions = action.split("/")[1:]
    find_cmd = re.compile(r'\w+')
    find_number = re.compile(r'\d+')
    for cmd in actions:
        try:
            current_command = find_cmd.search(cmd).group()
            if current_command not in commands:
                return
            if current_command == "accept":
                for commitid in find_number.findall(cmd):
                    repoid = db['ex'].get("commits", "repo", f'id="{commitid}"')[0]
                    branchid = db['ex'].get("commits", "branch", f'id="{commitid}"')[0]
                    db['ex'].get_repo(repoid).get_branch(branchid).get_commit(commitid).activate()

            if current_command == "invite":
                repo_to_join = find_number.search(cmd).group()
                db['ex'].get_repo(repo_to_join).add_owners(session['user'])
            if current_command == "branch_name_update":
                _, branch_id, name = cmd.split("*")
                rep = db['ex'].get("branches", "repo", f'id="{branch_id}"')[0]
                db['ex'].get_repo(rep).get_branch(branch_id).update_name(name)

        except Exception as e:
            print(f"Could not process command {cmd} | {e}")
        else:
            draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)


def get_messages(user):
    info = db['ex'].get_messages()
    if user in info['messages']:
        return [[message['id'], message['title'], message['content'], message['sender'], message['type']]
                for message in info['messages'][session['user']]]
    return []


@app.route("/inbox", methods=["POST", "GET"])
def inbox():
    clear_admin_images()
    if "user" not in session:
        return redirect(url_for("register"))
    if request.method == "POST":
        message_id = request.form['accept'] + request.form['mark_as_read']
        reaction = 'accept' if request.form['accept'] != "" else 'mark_as_read'
        # first grab the message to see what we need to do with it
        title, content, sender, receiver, msg_type, action = \
            db['ex'].get('messages', '*', f'id={message_id}', first=False)[0][1:]
        print(f"{reaction}: {title} | {msg_type}")
        if reaction != "mark_as_read":
            parse_action(action)

        db['ex'].remove("messages", f'id={message_id}')
    session['inbox_messages'] = get_messages(session['user'])
    return render_template("inbox.html")


def create_fork(fork_man):
    # we are forking the fork_man into a new thing :D
    bran = db['ex'].get('commits', 'branch', f'id={fork_man}')[0]
    repo = db['ex'].get('commits', 'repo', f'id={fork_man}')[0]
    new_owner = session['user']
    db['ex'].get_repo(repo).fork(bran, new_owner, fork_from_commit=fork_man)
    print(f"Successfully forked {fork_man}")
    # now the last commit in the database is the forked commit.
    # get its ID:
    latest = db['ex'].get("commits", "id")[-1]
    old_path = os.path.join(app.config['UPLOAD_FOLDER'],
                            f'{fork_man}',
                            f'{fork_man}.zip')
    new_commit_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                   f"{latest}")
    try:
        os.mkdir(new_commit_path)
    except FileExistsError:
        print("Folder is already there")
    else:
        print(f'Made folder for commit {new_commit_path}')

    # now copy the file
    shutil.copy(old_path, os.path.join(new_commit_path, f"{latest}.zip"))
    save_commit_manifest(latest, fork_man)
    draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    return render_template("repos.html")


def make_save_commit(s, files, name, commit_man, comment=""):
    comment = "No comment provided."

    if str(commit_man) == "0":
        flash(f"Didn't choose a commit")
        return render_template("repos.html")
    bran = db['ex'].get('commits', 'branch', f'id={commit_man}')[0]
    repo = s['repo_id'] = db['ex'].get('commits', 'repo', f'id={commit_man}')[0]
    branch_owner = db['ex'].get('branches', 'owner', f'id="{bran}"')[0]
    active = "1"
    if branch_owner != s['user'] and s['is_branch_head']:
        flash(f"A request has been sent to {branch_owner}")
        active = "0"

    if s['is_branch_head']:
        db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, s['user'],
                                                               previous=commit_man, activate=active)
    else:
        index = 0
        b = True
        new_bran = "Unnamed"
        while b:
            try:
                print(f"Trying index", index)
                new_bran = new_bran + ("" if index == 0 else f"_{index}")
                db['ex'].get_repo(repo).create_branch(new_bran, s['user'])
            except Exception as e:
                print(e)
                index += 1
                print("Error. Trying again!")
            else:
                b = False
                print("Success!")
                bran = new_bran
            # get an unused name
        db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, s['user'],
                                                               previous=commit_man, activate=active)

    flash(f"Succesfully commited {name}: {comment}" if comment != "" else "")
    try:
        a = files
    except:
        flash("Need to select a file")
        return render_template("repos.html")

    r_commits = db['ex'].get_repo(repo).get_branch(bran).get_commits()
    current_id = r_commits[-1].get_id()
    new_commit_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                   f"{current_id}")
    try:
        os.mkdir(new_commit_path)
    except FileExistsError:
        print("Folder is already there")
    else:
        print(f'Made folder for commit {new_commit_path}')
    for f in a:
        # save in temp folder, unpack, delete.
        extract_dir = os.path.join(app.config['UPLOAD_FOLDER'], f"{current_id}")
        try:
            os.mkdir(extract_dir)
        except Exception as e:
            print(f"There was an error creating the extract directory for commit {current_id}", e)
            pass
        filename = os.path.join(extract_dir, f"{current_id}.zip")
        f.save(filename)

    save_commit_manifest(current_id, commit_man)
    if active == "0":
        commit_to_message(branch_owner, name, comment, current_id, s['current_repo'],
                          s['branch_name'])
    draw_graph(to_highlight=s['to_highlight'], reload_colors=s['to_highlight'] == 0)
    return render_template("repos.html")


def file_history_full(commit_id, file_list):
    session['commit_file_histories'] = []
    for file in file_list:
        session['commit_file_histories'].append(input_file_history(commit_id, file))


def input_file_history(commit_id, path):
    # go through the commit chain and
    # scan everything, to check when the file has changed
    # or has been created.
    chain = db['ex'].get_commit_chain(commit_id)
    file_data = {}
    updated = re.compile(fr"^(updated|added).+{path}", flags=re.MULTILINE)
    for index in chain:
        fetch_path = os.path.join("user_files", f"{index}", f"{index}.zip")
        unpack_path = os.path.join("temp_zip", f"scanning_{index}_{time.time()}")
        with open(os.path.join("user_files", f"{index}", "manifest"), "rb") as f:
            manifest = f.read().decode()

        if not updated.search(manifest):
            # this means that the file was not updated this commit.
            continue

        try:
            os.mkdir(unpack_path)
        except Exception as e:
            print(f"Error making temp scan path for {index}: {e}")
            shutil.rmtree(unpack_path)
            os.mkdir(unpack_path)
        else:
            print(f"Scanning {index}...")
        shutil.unpack_archive(fetch_path, unpack_path)
        with open(os.path.join(unpack_path, path), "rb") as f:
            file_data[str(index)] = {"bytes": f.read().decode() if path.endswith(".txt") else "[Not a text file]",
                                     "commit name": db['ex'].get("commits", "commit_name", f'id="{index}"')[0]}

        shutil.rmtree(unpack_path)

    return file_data


@app.errorhandler(404)
def page_not_found(e):
    print(e)
    return render_template('404.html'), 404


@app.route("/admin", methods=["POST", "GET"])
def admin():
    # if user not logged in return to register page
    if "user" not in session:
        return redirect(url_for("register"))

    # if user not admin ("Dan Lvov") return to login page
    if session['user'] != db['ex'].admin:
        return redirect("/login"), 404
    else:
        try:
            os.remove("./static/admin_json.js")
        except:
            pass
        # loop over all repo IDs
        session['all_images'] = []
        for r_id in [a.id for a in db['ex'].repos]:
            draw_graph(0, True, False, admin_view=True, repo=r_id)
            creator, owners, name = db['ex'].get("repos", "creator, owners, name", f'id="{r_id}"', first=False)[0]
            session['all_images'].append((creator, owners, name, f"admin_{r_id}.png"))
        # the admin page has two mods. visual and json
        # first we draw the graph for every repo, and then
        # dump the entire database as a json file.
        # this way, we don't need to reload the page.
        with open("./static/admin_json.js", "w+") as f:
            f.write("var json_text = " + json.dumps(db['ex'].to_json()) + ";")
        return render_template("admin_view.html")


@app.route("/repos", methods=["POST", "GET"])
def repos():
    # no such user can exist
    user = ", asd,l; a-!"
    clear_admin_images()
    if "user" not in session:
        return redirect(url_for("register"))
    if "user" in session:
        user = session['user']
        session['repos'] = [[x[0], x[1]] for x in
                            db['ex'].get("repos", "id, name, owners", first=False) if x[2].find(user) != -1]
        if not request.form:
            session['to_highlight'] = 0

    # # # # # # # # # # # # # # # #
    #    User tries rendering     #
    # # # # # # # # # # # # # # # #
    session['current_commit_manifest'] = []
    session['current_commit_name'] = "No commit selected"
    session['current_commit_desc'] = ""
    session['current_commit_files'] = []

    if request.method == "POST":
        print("POST")
        session['repos'] = [[x[0], x[1]] for x
                            in db['ex'].get("repos", "id, name, owners", first=False) if x[2].find(user) != -1]
        # print(request.form)
        # print(request.files)
        # # # # # # # # # # # # # # # #
        #   Highlighting something    #
        # # # # # # # # # # # # # # # #

        if "repos" in request.form:
            session['repo_id'] = repo_id = request.form['repos']
            session['branch_names_list'] = db['ex'].get("branches", "name", f'repo="{repo_id}"', first=False)
            if session['repo_id'] == '':

                session['current_repo'] = ''
                session['repo_id'] = 0
                flash("You need to select a repo first")
            else:
                draw_graph()
            return render_template("repos.html")

        if 'new_branch_name' in request.form:
            nbn = request.form['new_branch_name']
            if nbn == "":
                return render_template("repos.html")
            if session['my_branch']:
                db['ex'].get_repo(session['repo_id']).get_branch(session["current_branch"]).update_name(nbn)
                flash(f"Changed {session['branch_name']} to {nbn}")
            else:
                message_title = f'{session["user"]} wants to rename ' \
                                f'{session["branch_name"]} in repo ' \
                                f'{session["current_repo"]}'
                message_desc = f'Old name: {session["branch_name"]} | New name: {nbn}'
                message_sender = session['user']
                receiver = session['branch_owner']
                message_type = "question"
                action = f"/rename*{session['current_branch']}*{nbn}"

                db['ex'].send_message(message_title, message_desc, message_sender, receiver, message_type, action)

                flash(f"Sent a request to {receiver}!")
            return render_template("repos.html")

        if 'fork_man' in request.form:
            create_fork(request.form['fork_man'])
            return render_template("repos.html")

        if 'user_to_add' in request.form:
            if request.form['user_to_add'] not in db['ex'].get_all_names():
                flash("That's not a user! >:(")
            else:
                db['ex'].grant_ownership(request.form['user_to_add'], str(session['repo_id']))
            return render_template("repos.html")

        if 'user_to_add' in request.form:
            name = request.form['user_to_add']
            db['ex'].get_repo(session['repo_id']).add_owners(name)
            return render_template("repos.html")

        if 'name' in request.form:
            c = ""
            if 'comment' in request.form:
                c = request.form['comment']
            make_save_commit(session, request.files.getlist("file"), request.form['name'], request.form['commit_man'],
                             c)
            return render_template("repos.html")

        if "history_file_path" in request.form:
            session['history_file_path'] = input_file_history(session['to_highlight'],
                                                              request.form["history_file_path"])
            return render_template("repos.html")

        if "merge-confirm" in request.form:

            rep = db['ex'].get_repo(session['repo_id'])
            receiving_branch = session['parent_branch_id']
            previous_id = db['ex'] \
                .get_repo(db['ex'].get("branches", "repo", f'id="{receiving_branch}"')[0]) \
                .get_branch(session['parent_branch_id']) \
                .head.id

            prev_name = db['ex'].get('commits', 'commit_name', f'id={previous_id}')[0]

            # after getting the last one we make the murge in the database

            rep.merge(session['current_branch'],
                      session['parent_branch_id'],
                      session['user'],
                      activated=session['user'] == db['ex'].get("branches", "owner", f'id="{receiving_branch}"'))

            after_merge_id = db['ex'].get('commits', 'id')[-1]

            merger_id = session['to_highlight']

            commit_path = os.path.join("user_files", f"{after_merge_id}")

            try:
                os.mkdir(commit_path)
            except Exception as e:
                print(f"There was an error creating the folder for the merged commit {after_merge_id}")
                print(e)
                pass
            else:
                print(f"Created {commit_path} merge commit folder")
            merger_path = os.path.join("temp_zip", f"merging_{after_merge_id}_{str(time.time()).replace('.', '')}")

            try:
                os.mkdir(merger_path)
            except Exception as e:
                print(f"There was an error creating the folder for the temp merged commit {after_merge_id}")
                print(e)
                pass
            else:
                print(f"Began merging {merger_id} and {previous_id}")
            merger_files, merger_scan_path = get_commit_files(merger_id)
            previous_files, previous_path = get_commit_files(previous_id)

            merged_directories = merge_dictionaries(merger_files, previous_files)
            print_dir(merged_directories)

            for directory in merged_directories:
                a = os.path.join(merger_path, directory[1:])
                try:
                    os.mkdir(a)
                except Exception as e:
                    if directory not in ["", "/"]:
                        print(f"There was an error creating the folder for the temp merged commit {after_merge_id}")
                        print(e)
                    pass
                for file in merged_directories[directory]:
                    # file = [name, data]
                    name = file[0]
                    data = file[1]
                    print(f"Attempting to write to {os.path.join(a, name)}.")
                    with open(os.path.join(a, name), "w+b") as f:
                        f.write(data.read())
                    data.close()
                    #  my merge function should have done this but i'm too lazy deal with it

            shutil.rmtree(merger_scan_path)
            shutil.rmtree(previous_path)

            shutil.make_archive(os.path.join(commit_path, f"{after_merge_id}"), "zip", root_dir=merger_path)

            shutil.rmtree(merger_path)
            manifest = save_commit_manifest(after_merge_id, previous_id, merge=True)

            if not session['my_branch']:
                message_title = f'{session["user"]} wants to rename ' \
                                f'merge commit id #{previous_id} : {prev_name} in repo ' \
                                f'{session["current_repo"]}'
                message_desc = f'Delta: {manifest}'
                message_sender = session['user']
                receiver = session['branch_owner']
                message_type = "question"
                action = f"/accept*{after_merge_id}"

                db['ex'].send_message(message_title, message_desc, message_sender, receiver, message_type, action)
                flash(f"A request has been sent to {session['branch_owner']}")
                return render_template("repos.html")

        try:
            if 'to_highlight' in request.form:
                session['to_highlight'] = c_id = request.form['to_highlight']
                session['is_branch_head'] = str(
                    db['ex'].get('commits', 'next_commit', f'id={session["to_highlight"]}')[0]) == "-1"
                session['repo_id'] = repo_id = db["ex"].get("commits", "repo", f'id="{session["to_highlight"]}"')[0]
                session['current_repo'] = db['ex'].get("repos", "name", condition=f'id="{repo_id}"')[0]
                branch_id = db["ex"].get("commits", "branch", f'id="{session["to_highlight"]}"')[0]
                session['current_branch'] = branch_id
                session['my_branch'] = session['user'] in db['ex'].get("branches", "owner", f'id="{branch_id}"')[0]
                session['branch_name'] = db["ex"].get("branches", "name", f'id="{branch_id}"')[0]
                session['branch_owner'] = db["ex"].get("branches", "owner", f'id="{branch_id}"')[0]
                # we now find the parent branch
                session['parent_branch_id'] = None
                session['parent_branch_name'] = None
                c_b_id = branch_id
                prev_b_id = None
                gotem = False
                while str(c_id) != "-1":
                    c_b_id = db['ex'].get("commits", "branch", f'id="{c_id}"')[0]
                    c_id = db['ex'].get("commits", "previous_commit", f'id="{c_id}"')[0]
                    try:
                        prev_b_id = db['ex'].get("commits", "branch", f'id="{c_id}"')[0]
                        if c_b_id > prev_b_id:
                            gotem = True
                            session['parent_branch_id'] = prev_b_id
                            session['parent_branch_name'] = db['ex'].get("branches", "name", f'id="{prev_b_id}"')[0]
                            break
                    except:
                        break
                if gotem:
                    prev_b_head_id = db['ex'] \
                        .get_repo(session["repo_id"]) \
                        .get_branch(session['parent_branch_id']) \
                        .head.id

                    session['commit_diff'] = \
                        generate_commit_diff(session['to_highlight'],
                                             prev_b_head_id,
                                             merge=True,
                                             output_mode=1)


            else:
                session['repo_id'] = request.form["commit_man"]
        except Exception as e:
            if str(
                    e) != "400 Bad Request: The browser (or proxy) sent a request that this server could not understand.":
                print(e)
        # now we need to copy the current commit file to the static folder
        # first we clear it
        path_temp = os.path.join(os.getcwd(), "static", "current_files", session['user'])
        fetch_path = os.path.join(os.getcwd(), "user_files", f"{session['to_highlight']}",
                                  f"{session['to_highlight']}.zip")
        try:
            os.mkdir(path_temp)
        except Exception:
            print("Did not need to remake current_files folder")
            pass
        else:
            print("Created the current_files folder since it was deleted.")
        # clear temp folder.
        for root, dirs, files in os.walk(path_temp):
            for f in files:
                os.unlink(os.path.join(root, f))
            for d in dirs:
                shutil.rmtree(os.path.join(root, d))
        print("Cleared temp folder for user")
        # unpack the current commit zip into the temp folder.
        try:
            shutil.unpack_archive(fetch_path, path_temp)
            shutil.copy(fetch_path, path_temp)
            os.rename(os.path.join(path_temp, f"{session['to_highlight']}.zip"),
                      os.path.join(path_temp, f"commit_zip.zip"))
        except Exception as e:
            print("Unpacking error ", e)
        x = session['to_highlight']
        if str(x) != "0":
            try:
                session['current_commit_name'] = db["ex"].get("commits", "commit_name", f'id="{x}"')[0]
                session['current_commit_desc'] = db["ex"].get("commits", "comment", f'id="{x}"')[0]
                f_list = session['current_commit_files'] = list_commit_files()
                session['zipped_files_indexes'] = [(file, index) for index, file in enumerate(f_list)]
                session['current_commit_manifest'] = read_commit_manifest(x)
                file_history_full(session['to_highlight'], f_list)
            except Exception as e:
                print(e)

        draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    else:
        session['current_commit_name'] = "No commit selected"
        session['current_commit_desc'] = ""
        try:
            print("Erasing picture")
            # graphics_manager.start_draw(session, erase=True)
            draw_graph(session['to_highlight'], reload_colors=True, erase_var=True)
        except Exception as e:
            print(e)

    # # # # # # # # # # # # # # # #
    #   Simply loading the page   #
    # # # # # # # # # # # # # # # #

    return render_template("repos.html")


@app.route("/users")
def users():
    if "user" not in session:
        return redirect(url_for("register"))
    if session['user'] != db['ex'].admin:
        return redirect("/login"), 404

    users = [(x[0], x[2]) for x in db['ex'].get_users()]
    json_ret = []
    for user, owned in users:
        ow = [db['ex'].get_repo(x).to_json() for x in owned.split(", ") if x.strip() != ""]
        json_ret.append({
            F"{user}": ow
        })
    _ = db['ex'].to_json()
    return json.dumps(db['ex'].to_json(), indent=3)


if __name__ == "__main__":
    socketio.run(app)

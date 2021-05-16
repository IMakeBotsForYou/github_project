import os
import re
import shutil
import time
from os.path import join

from cryptography.fernet import Fernet
from flask import *
from flask_socketio import SocketIO
from database_manager import reformat
import database_manager
import graphics_designer

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


@app.route("/")
def home():
    # If user is logged in
    if "user" in session:
        session['current_repo'] = 0
        return redirect(url_for("repos"))
    # If they're not logged in, log in.
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
            db['ex'].add_user(user, db['key'].encrypt(password.encode()).decode(), [])
            return redirect(url_for(f"repos"))
        return render_template("register.html")
    else:
        return render_template("register.html")


@app.route("/create_repo", methods=["POST", "GET"])
def create_repo():
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
        repo_id = db['ex'].get("repos", "id", f'name="{repo_name}"')[0]
        repo_first_commit = db['ex'].get("commits", "id", f'repo={repo_id}')[0]

        new_commit_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                       f"{repo_first_commit}")
        try:
            os.mkdir(new_commit_path)
        except FileExistsError:
            print("Folder is already there")
        else:
            print(f'Made folder for commit {new_commit_path}')

        generate_commit_manifest(repo_first_commit)
        graphics_designer.start_draw(session, to_highlight=None,
                                     reload_colors=True, force=True)
        return redirect(url_for("repos"))
    return render_template("create_repo.html")


@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        user = request.form['name']
        # password = db['key'].encrypt(request.form['pass'].encode()).decode()
        password = request.form['pass']
        all_names = db['ex'].get_all_names()
        # Is the password correct? Is the user valid?
        if user not in all_names or db['ex'].get("users", "password", f'name="{user}"')[0] != password:
            flash("Either the name, or the password are wrong.")
            return render_template("login.html")
        else:
            session['user'] = user

            # create the instance folder
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            return redirect(f"/repos")
    else:
        return render_template("login.html")


@app.route('/logout')
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


def commit_to_message(files, receiver, title, desc, current_id, previous, repo, branch):
    # add commit to queue
    message_title = f'{session["user"]} has suggested {title} in repo {repo} - {branch}'
    message_desc = f"{desc}\n" + \
                   f"Commit delta:\n" + \
                   open(f"./user_files/{current_id}/manifest", 'rb').read().decode()
    message_sender = session['user']
    message_type = "question"
    action = f"/accept*{current_id}"

    db['ex'].add("messages (title, content, sender, receiver, type, action)",
                 reformat((message_title, message_desc, message_sender, receiver, message_type, action)))


def make_image_map():
    data = db['ex']
    try:
        branches = data.get_repo(session['current_repo']).get_branches()
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
    except:
        pass
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


def generate_commit_manifest(current_id):
    try:
        previous_id = db['ex'].get("commits", "id", f'next_commit="{current_id}"')
        is_next_to = db['ex'].get("commits", "previous_commit", f'id="{current_id}"')

        if str(is_next_to) == "-1" and not previous_id:
            raise IndexError
        else:
            previous_id = is_next_to[0]
        previous_files = get_commit_files(previous_id)
    except IndexError:
        current_rp_name = db['ex'].get("repos", "name", f'id=1')[0]
        manifest = 'created repo "' + current_rp_name + '"'
        with open(join(app.config['UPLOAD_FOLDER'], f"{current_id}", "manifest"), "w+b") as f:
            f.write(manifest.encode())
        print(f"Created manifest for commit #{current_id}:\n{manifest}")
        return
    # get current files
    current_files = get_commit_files(current_id)
    manifest = ""
    # First we check all current directories -> last commit | To check adds / edits
    # then last commit -> current | To check deletes
    for directory in current_files:
        directory = directory.replace("\\", "/")
        no_slash_dir = directory[1:]
        if directory not in previous_files:
            # we created a directory, along with all its files.
            manifest += f"created {no_slash_dir if directory != '/' else 'root directory'}\n"
            for file in [data[0] for data in current_files[directory]]:
                manifest += f"added {no_slash_dir}/{file}\n"
        else:
            previous_names = [data[0] for data in previous_files[directory]]
            current_names = [data[0] for data in current_files[directory]]
            for file in current_files[directory]:
                name = file[0]
                data = file[1]
                if name == "manifest":
                    continue
                if name not in previous_names:
                    manifest += f"added {no_slash_dir}{name}\n"
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
                        manifest += f"updated {no_slash_dir}{name}\n"
            for name in [name for name in previous_names if name not in current_names]:
                manifest += f"deleted {no_slash_dir}{name}\n"

        if previous_files:
            _ = [data[1].close() for data in previous_files[directory]]
        if current_files:
            _ = [data[1].close() for data in current_files[directory]]

    with open(join(app.config['UPLOAD_FOLDER'], f"{current_id}", "manifest"), "w+b") as f:
        f.write(manifest.encode())
    print(f"Created manifest for commit #{current_id}:\n{manifest}")

    shutil.rmtree(os.path.join("temp_zip", f"reading_{current_id}"))
    shutil.rmtree(os.path.join("temp_zip", f"reading_{previous_id}"))


def read_commit_manifest(commit_id):
    lines = []
    try:
        file = open(join(app.config['UPLOAD_FOLDER'], f"{commit_id}", "manifest"), "rb")
        lines = file.read().decode().split("\n")
    except:
        flash("There was an error loading the changes file.")
    data = []
    for line in lines:
        action = line.split(" ")[0]
        if action != "":
            data.append(
                {"action": action,
                 "rest": line[len(action) + 1:]
                 })
    return data


def get_commit_files(commit_id):
    ret = {}
    path = os.path.join(app.config['UPLOAD_FOLDER'],
                        f"{commit_id}", f"{commit_id}.zip")
    unpack_path = os.path.join("temp_zip", f"reading_{commit_id}")

    try:
        os.mkdir(unpack_path)
    except Exception as e:
        print(f"Error making temp unpack path for {commit_id}: {e}")
    else:
        print(f"Created temp unpack path for {commit_id}")

    try:
        shutil.unpack_archive(path, unpack_path)
    except shutil.ReadError:
        return ret
    else:
        print(f"Unpacked into reading_{commit_id}")
    for root, dirs, files in os.walk(unpack_path):
        for file in files:
            root = root.replace("\\", "/")
            root = root.replace("//", "/")
            # \\\\ -> / could work but i'm lazy

            # append the file name to the list
            if file != "manifest":
                directory = root[len(path):]
                location = os.path.join(root, file)
                if directory in ret:
                    ret[directory].append((file, open(location, 'rb')))
                else:
                    ret[directory] = [(file, open(location, 'rb'))]
    return ret


def list_commit_files():
    # path = join(app.config['UPLOAD_FOLDER'], f"{commit_id}")
    path = join("static", "current_files", session['user'])
    filelist = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # append the file name to the list
            if file != "commit_zip.zip":
                filelist.append(os.path.join(root, file)[len(path) + 1:].replace("\\", "/")
                                .replace("//", "/"))
    return filelist


def draw_graph(to_highlight=None, reload_colors=True, erase_var=False):
    try:
        session['image_size'] = graphics_designer.start_draw(session, to_highlight,
                                                             reload_colors, force=True, erase=erase_var)
        if not session['image_size']:
            raise ValueError("No fuckin size")
    except Exception as e:
        print(e)
        graphics_designer.start_draw(session, erase=True)
        flash("There has been an error loading this repo.")
        session['image_size'] = [0, 0]
    # request.form['repos'] => current repo id
    try:
        make_image_map()
        # remove cashing
        reload_image()
    except Exception as e:
        flash(f'Error - {e}')


def parse_action(action):
    commands = ["merge", "commit", "accept"]
    actions = action.split("/")[1:]
    find_cmd = re.compile(r'\w+')
    find_number = re.compile(r'\d+')
    for cmd in actions:
        try:
            current_command = find_cmd.search(cmd).group()
            if current_command not in commands:
                return
            if current_command == "accept":
                for num in find_number.findall(cmd):
                    db['ex'].edit("commits", "active", "1", f'id="{num}"')
            if current_command == "invite":
                repo_to_join = find_number.search(cmd).group()
                db['ex'].get_repo(repo_to_join).add_owners(session['user'])
                # session['current_repo'] = repo_to_join

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
    generate_commit_manifest(latest)
    draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    return render_template("repos.html")


def make_save_commit(session, files, name, commit_man, comment=""):
    comment = "No comment provided."

    if str(commit_man) == "0":
        flash(f"Didn't choose a commit")
        return render_template("repos.html")
    bran = db['ex'].get('commits', 'branch', f'id={commit_man}')[0]
    repo = session['current_repo'] = db['ex'].get('commits', 'repo', f'id={commit_man}')[0]
    branch_owner = db['ex'].get('branches', 'owner', f'id="{bran}"')[0]
    active = "1"
    if branch_owner != session['user']:
        flash(f"A request has been sent to {branch_owner}")
        active = "0"

    if session['is_branch_head']:
        db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, session['user'],
                                                               previous=commit_man, activate=active)
    else:
        index = 0
        b = True
        new_bran = "Unnamed"
        while b:
            try:
                print(f"Trying index", index)
                new_bran = db['ex'].get('branches', 'name', f'id="{bran}"')[0] + \
                           "_fork" + \
                           ("" if index == 0 else f"_{index}")
                db['ex'].get_repo(repo).create_branch(new_bran, session['user'])
            except Exception as e:
                print(e)
                index += 1
                print("Error. Trying again!")
            else:
                b = False
                print("Success!")
                bran = new_bran
            # get an unused name
        db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, session['user'],
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

    generate_commit_manifest(current_id)
    if active == "0":
        commit_to_message(files, branch_owner, name, comment, current_id, commit_man, session['current_repo'], session['branch_name'])
    draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    return render_template("repos.html")


@app.route("/repos", methods=["POST", "GET"])
def repos():
    # no such user can exist
    user = ", asd,l; a-!"
    if "user" not in session:
        return redirect(url_for("login"))
    if "user" in session:
        user = session['user']
        session['repos'] = [[x[0], x[1]] for x in
                            db['ex'].get("repos", "id, name, owners", first=False) if x[2].find(user) != -1]
        session['to_highlight'] = 0

    # # # # # # # # # # # # # # # #
    #    User tries rendering     #
    # # # # # # # # # # # # # # # #
    session['current_commit_manifest'] = []
    session['my_branch'] = True
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
            session['current_repo'] = request.form['repos']
            if session['current_repo'] == '':
                flash("You need to select a repo first")
            else:
                draw_graph()
            return render_template("repos.html")

        if 'new_branch_name' in request.form:
            nbn = request.form['new_branch_name']
            if nbn == "":
                return render_template("repos.html")
            db['ex'].edit("branches", "name", nbn, f'id="{session["current_branch"]}"')
            flash(f"Changed {session['branch_name']} to {nbn}")

        if 'fork_man' in request.form:
            create_fork(request.form['fork_man'])

        if 'user_to_add' in request.form:
            if request.form['user_to_add'] not in db['ex'].get_all_names():
                flash("That's not a user! >:(")
            else:
                print(session)
                db['ex'].grant_ownership(request.form['user_to_add'], str(session['repo_id']))
            return render_template("repos.html")

        if 'name' in request.form:
            c = ""
            if 'comment' in request.form:
                c = request.form['comment']
            make_save_commit(session, request.files.getlist("file"), request.form['name'], request.form['commit_man'],
                             c)

        try:
            if 'to_highlight' in request.form:
                session['to_highlight'] = request.form['to_highlight']
                session['is_branch_head'] = str(
                    db['ex'].get('commits', 'next_commit', f'id={session["to_highlight"]}')[0]) == "-1"
                session['repo_id'] = repo_id = db["ex"].get("commits", "repo", f'id="{session["to_highlight"]}"')[0]
                session['current_repo'] = db['ex'].get("repos", "name", condition=f'id="{repo_id}"')[0]
                branch_id = db["ex"].get("commits", "branch", f'id="{session["to_highlight"]}"')[0]
                session['current_branch'] = branch_id
                session['my_branch'] = session['user'] in db['ex'].get("branches", "owner", f'id="{branch_id}"')[0]
                session['branch_name'] = db["ex"].get("branches", "name", f'id="{branch_id}"')[0]
                session['branch_owner'] = db["ex"].get("branches", "owner", f'id="{branch_id}"')[0]
            else:
                repo_id = request.form["commit_man"]
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
        except Exception as e:
            print(e)
            pass
        x = session['to_highlight']
        if str(x) != "0":
            try:
                session['current_commit_name'] = db["ex"].get("commits", "commit_name", f'id="{x}"')[0]
                session['current_commit_desc'] = db["ex"].get("commits", "comment", f'id="{x}"')[0]
                session['current_commit_files'] = list_commit_files()
                session['current_commit_manifest'] = read_commit_manifest(x)
            except Exception as e:
                print(e)

        if 'user_to_add' in request.form:
            name = request.form['user_to_add']
            db['ex'].get_repo(session['current_repo']).add_owners(name)
        draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    else:
        session['current_commit_name'] = "No commit selected"
        session['current_commit_desc'] = ""
        try:
            print("Erasing picture")
            # graphics_designer.start_draw(session, erase=True)
            draw_graph(session['to_highlight'], reload_colors=True, erase_var=True)
        except Exception as e:
            print(e)
    # # # # # # # # # # # # # # # #
    #   Simply loading the page   #
    # # # # # # # # # # # # # # # #

    return render_template("repos.html")


@app.route("/users")
def users():
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
    key = Fernet.generate_key()
    db['key'] = Fernet(key)
    socketio.run(app)

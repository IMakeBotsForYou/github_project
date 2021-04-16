from flask import *
import database_manager
import graphics_designer
from cryptography.fernet import Fernet
from flask_socketio import SocketIO
import os
import time
import re
from os import listdir
from os.path import isfile, join
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
import shutil
from zipfile import ZipFile

app = Flask(__name__)
if __name__ == "__main__":
    app.secret_key = b'_5y2L"\xea2L"F4Q8z\n\xec]\ny2L"F4Q8z\n\xec]]#y2L"F4Q8z\n\xec]/'
    socketio = SocketIO(app)
    database_manager.main()
    db = {"ex": database_manager.my_db}
    app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), "user_files")


@app.route("/")
def home():
    if "user" in session:
        session['current_repo'] = 0
        return redirect(url_for("repos"))
    return redirect(url_for("login"))


@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
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
            session['reloads'] = 0
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
        owners = list(set([name.strip() for name in request.form['owners'].split(",") if
                           name.strip() != "" and name.strip() in actual_names] + [creator]))
        db['ex'].create_repository(repo_name, owners, creator)

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
        password = request.form['pass']
        all_names = db['ex'].get_all_names()
        if user not in all_names or db['ex'].get("users", "password", f'name="{user}"')[0] != password:
            flash("Either the name, or the password are wrong.")
            return render_template("login.html")
        else:
            session['user'] = user
            session['reloads'] = 0

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


def make_image_map():
    data = db['ex']
    branches = data.get_repo(session['current_repo']).get_branches()
    areas = []
    for b in branches:
        areas += [[x.get_id(), b.get_id()] for x in b.get_commits()]
    x = sorted(areas, key=lambda x: x[0])
    for i, b in enumerate(x):
        x[i].append(i)
    session['areas'] = x


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

    session['path'] = new_name


def generate_commit_manifest(current_id):
    try:
        previous_id = db['ex'].get("commits", "id", f'next_commit="{current_id}"')[0]
        if str(previous_id) == "-1":
            raise IndexError
        else:
            previous_id = db['ex'].get("commits", "previous_commit", f'id="{current_id}"')[0]
        previous_files = get_commit_files(previous_id)
    except IndexError:
        # current_rp_name = db['ex'].get("repos", "name", f'id={session["current_repo"]}')[0]
        current_rp_name = db['ex'].get("repos", "name", f'id=1')[0]
        manifest = 'created repo "' + current_rp_name + '"'
        with open(join(app.config['UPLOAD_FOLDER'], f"{current_id}", "manifest"), "w+") as f:
            f.write(manifest)
        print(f"Created manifest for commit #{current_id}:\n{manifest}")
        return

    current_files = get_commit_files(current_id)
    manifest = ""
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
                if name in ["commit_zip.zip", "manifest"]:
                    continue
                if name not in previous_names:
                    manifest += f"added {no_slash_dir}{name}\n"
                else:
                    print(name)
                    current_bytes = data.read()

                    previous_data = [data[1] for data in previous_files[directory] if data[0] == name][0]
                    previous_bytes = previous_data.read()

                    if current_bytes != previous_bytes:
                        manifest += f"updated {no_slash_dir}{name}\n"
            for name in [name for name in previous_names if name not in current_names]:
                manifest += f"deleted {no_slash_dir}{name}\n"
    with open(join(app.config['UPLOAD_FOLDER'], f"{current_id}", "manifest"), "w+") as f:
        f.write(manifest)
    print(f"Created manifest for commit #{current_id}:\n{manifest}")


def read_commit_manifest(commit_id):
    lines = []
    try:
        file = open(join(app.config['UPLOAD_FOLDER'], f"{commit_id}", "manifest"))
        lines = file.read().split("\n")
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
                        f"{commit_id}")

    for root, dirs, files in os.walk(path):
        for file in files:
            root = root.replace("\\", "/")
            root = root.replace("//", "/")
            # \\\\ -> / could work but i'm lazy

            # append the file name to the list
            if file != "manifest" and file != "commit_zip.zip":
                directory = root[len(path):]
                location = os.path.join(root, file)
                if directory in ret:
                    ret[directory].append((file, open(location)))
                else:
                    ret[directory] = [(file, open(location))]
    return ret


def list_commit_files(commit_id):
    path = join(app.config['UPLOAD_FOLDER'], f"{commit_id}")
    filelist = []
    for root, dirs, files in os.walk(path):
        for file in files:
            # append the file name to the list
            if file != "manifest" and file != "commit_zip.zip":
                filelist.append(os.path.join(root, file)[len(path) + 1:].replace("\\", "/")
                                                                        .replace("//", "/"))
    return filelist


def draw_graph(to_highlight=None, reload_colors=True):
    try:
        session['image_size'] = graphics_designer.start_draw(session, to_highlight,
                                                             reload_colors, force=True)
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
                for number in find_number.findall(cmd):
                    db['ex'].move_from_queue(number)

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
        id = request.form['accept'] + request.form['mark_as_read']
        reaction = 'accept' if request.form['accept'] != "" else 'mark_as_read'
        # first grab the message to see what we need to do with it
        title, content, sender, receiver, msg_type, action = db['ex'].get('messages', '*', f'id={id}', first=False)[0][
                                                             1:]
        print(f"{reaction}: {title} | {msg_type}")
        if reaction != "mark_as_read":
            parse_action(action)

        db['ex'].remove("messages", f'id={id}')
    session['inbox_messages'] = get_messages(session['user'])
    return render_template("inbox.html")


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
    session['hightlighed'] = 0
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
            session['current_repo'] = request.form['repos']
            if session['current_repo'] == '':
                flash("You need to select a repo first")
            else:
                draw_graph()
            return render_template("repos.html")

        try:
            session['to_highlight'] = request.form['to_highlight']
            repo_id = db["ex"].get("commits", "repo", f'id="{session["to_highlight"]}"')[0]
            session['current_repo'] = db['ex'].get("repos", "name", condition=f'id="{repo_id}"')[0]

            # now we need to copy the current commit file to the static folder
            # first we clear it
            path_temp = os.path.join(os.getcwd(), "static", "current_files")
            fetch_path = os.path.join(os.getcwd(), "temp_zip", f"{session['to_highlight']}.zip")

            shutil.rmtree(path_temp)

            shutil.unpack_archive(fetch_path, path_temp)

        except Exception as e:
            print(e)
            pass
        x = session['to_highlight']
        if str(x) != "0":
            try:
                session['current_commit_name'] = db["ex"].get("commits", "commit_name", f'id="{x}"')[0]
                session['current_commit_desc'] = db["ex"].get("commits", "comment", f'id="{x}"')[0]
                session['current_commit_files'] = list_commit_files(int(x))
                session['current_commit_manifest'] = read_commit_manifest(x)
            except Exception as e:
                print(e)

        # print(request.form)
        # print(session)
        if 'user_to_add' in request.form:
            name = request.form['user_to_add']
            db['ex'].get_repo(session['current_repo']).add_owners(name)

        if 'name' in request.form:
            name = request.form['name']
            comment = "No comment provided."
            if 'comment' in request.form:
                comment = request.form['comment']

            if str(request.form["commit_man"]) == "0":
                flash(f"Didn't choose a commit")
                return render_template("repos.html")
            bran = db['ex'].get('commits', 'branch', f'id={request.form["commit_man"]}')[0]
            repo = session['current_repo'] = db['ex'].get('commits', 'repo', f'id={request.form["commit_man"]}')[0]
            db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, session['user'],
                                                                   previous=request.form["commit_man"])
            flash(f"Succesfully commited {name}: {comment}")
            a = request.files.getlist("file")
            r_commits = db['ex'].get_repo(repo).get_branch(bran).get_commits()
            print([x.get_id() for x in r_commits])
            current_id = r_commits[-1].get_id()
            new_commit_path = os.path.join(app.config['UPLOAD_FOLDER'],
                                           f"{current_id}")
            try:
                os.mkdir(new_commit_path)
            except FileExistsError:
                print("Folder is already there")
            else:
                print(f'Made folder for commit {new_commit_path}')
            # path_to_zip = os.path.join(new_commit_path, "commit_zip.zip")
            for f in a:
                # save in temp folder, unpack, delete.
                temp = os.path.join(os.getcwd(), "temp_zip")
                extract_dir = os.path.join(app.config['UPLOAD_FOLDER'],  f"{current_id}")
                try:
                    os.mkdir(temp)
                    os.mkdir(extract_dir)
                except FileExistsError:
                    print("Folder is already there")
                except Exception as e:
                    continue
                filename = os.path.join(temp, f"{current_id}.zip")
                f.save(filename)
                shutil.unpack_archive(filename, extract_dir)

            generate_commit_manifest(current_id)
            draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
            return render_template("repos.html")

        draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    else:
        session['current_commit_name'] = "No commit selected"
        session['current_commit_desc'] = ""
        try:
            print("Erasing picture")
            graphics_designer.start_draw(session, erase=True)
        except Exception as e:
            print(e)
            pass
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

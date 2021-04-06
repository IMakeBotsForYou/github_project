from flask import *
from database_manager import Database
from cryptography.fernet import Fernet
import graphics_designer
from flask_socketio import SocketIO
import os
import re
from os import listdir
from os.path import isfile, join
from werkzeug.utils import secure_filename

# instance_path='/user_files'
app = Flask(__name__)
app.secret_key = b'_5y2L"\xea2L"F4Q8z\n\xec]\ny2L"F4Q8z\n\xec]]#y2L"F4Q8z\n\xec]/'
socketio = SocketIO(app)
db = {"ex": Database("databases/database")}
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), "user_files")


@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r


@app.route("/")
def home():
    if "user" in session:
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
        owners = [name.strip() for name in request.form['owners'].split(",") if name.strip() != "" and name in actual_names]
        db['ex'].create_repository(repo_name, owners, creator)
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
    pathy = os.getcwd() + "\\static\\" + our_file
    numb = int(re.search(r"\d+", our_file).group())
    session['reloads'] = numb
    x = pathy[:-4 - len(str(numb))] + f"{numb + 1}.png"
    try:
        os.remove(x)
    except:
        pass
    os.rename(pathy, x)
    try:
        os.remove(pathy)
    except:
        pass
    session['path'] = re.search(rf"rendered_{session['user']}_\d+\.png", x).group()


def generate_commit_manifest(current_id):
    previous_id = db['ex'].get("commits", "id", f'next_')


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
                 "rest": line[len(action)+1:]
                 })
    return data


def read_commit_files(commit_id):
    path = join(app.config['UPLOAD_FOLDER'], f"{commit_id}")
    onlyfiles = [f for f in listdir(path) if isfile(join(path, f))]
    return onlyfiles


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
    make_image_map()
    # remove cashing
    reload_image()


def parse_action(action, requester):
    commands = ["merge", "commit"]
    actions = action.split("/")[1:]
    find_cmd = re.compile(r'\w+')
    find_number = re.compile(r'\d+')
    for cmd in actions:
        try:

            current_command = find_cmd.search(cmd).group()
            if current_command not in commands:
                return
            if current_command == "merge":
                start, dest = find_number.findall(cmd)
                current_repo, start_b = db['ex'].get("commits", "repo, branch", f'id={start}', first=False)[0]
                dest_b = db['ex'].get("commits", "branch", f'id={dest}')[0]
                db['ex'].get_repo(current_repo).merge(start_b, dest_b, requester)
            if current_command == "commit":
                # name, comment, creator, previous
                name, comment, creator, previous = cmd[6:].split("*")
                # previous is of the same branch.
                r, b = db['ex'].get("commits", "repo, branch", condition=f'id={previous}')
                db['ex'].get_repo(r).get_branch(b).create_commit(name, comment, creator, previous)
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
        title, content, sender, receiver, msg_type, action = db['ex'].get('messages', '*', f'id={id}', first=False)[0][1:]
        print(f"{reaction}: {title} | {msg_type}")
        if reaction != "mark_as_read":
            parse_action(action, sender)
            reload_image()
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

    if request.method == "POST":
        session['repos'] = [[x[0], x[1]] for x
                            in db['ex'].get("repos", "id, name, owners", first=False) if x[2].find(user) != -1]
        session['hightlighed'] = 0
        session['to_highlight'] = 0
        session['current_repo'] = 0
        session['current_commit_manifest'] = []
        session['current_commit_name'] = "No commit selected"
        session['current_commit_desc'] = ""
        # print(request.form)
        # print(request.files)
        # # # # # # # # # # # # # # # #
        #   Highlighting something    #
        # # # # # # # # # # # # # # # #
        if "repos" in request.form:
            session['current_repo'] = request.form['repos']
            if session['current_repo'] == '':
                flash("You need to select a repo first")
                return render_template("repos.html")

        try:
            session['to_highlight'] = request.form['to_highlight']
            repo_id = db["ex"].get("commits", "repo", f'id="{session["to_highlight"]}"')[0]
            session['current_repo'] = db['ex'].get("repos", "name", condition=f'id="{repo_id}"')[0]
        except:
            pass
        x = session['to_highlight']
        if str(x) != "0":
            try:
                session['current_commit_name'] = db["ex"].get("commits", "commit_name", f'id="{x}"')[0]
                session['current_commit_desc'] = db["ex"].get("commits", "comment", f'id="{x}"')[0]
                session['current_commit_files'] = read_commit_files(int(x))
                session['current_commit_manifest'] = read_commit_manifest(x)
            except Exception as e:
                print(e)

        # print(request.form)
        # print(session)

        if 'name' in request.form:
            name = request.form['name']
            comment = "No comment provided."
            if 'comment' in request.form:
                comment = request.form['comment']

            if str(request.form["commit_man"]) == "0":
                flash(f"Didn't choose a commit")
                return render_template("repos.html")
            bran = db['ex'].get('commits', 'branch', f'id={request.form["commit_man"]}')[0]
            db['ex'].get_repo(session["current_repo"]).get_branch(bran).create_commit(name, comment, session['user'],
                                                                                      previous=request.form["commit_man"])
            flash(f"Succesfully commited {name}: {comment}")
            a = request.files.getlist("file")
            for f in a:
                f.save(os.path.join(session["files_path"], secure_filename(f.filename)))
            return render_template("repos.html")

        draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight'] == 0)
    else:
        session['current_commit_name'] = "No commit selected"
        session['current_commit_desc'] = ""
        try:
            graphics_designer.start_draw(session, erase=True)
        except Exception as e:
            print(e)
            pass
        reload_image()
    # # # # # # # # # # # # # # # #
    #   Simply loading the page   #
    # # # # # # # # # # # # # # # #
    return render_template("repos.html")


@app.route("/users")
def users():
    users = [(x[0], x[2]) for x in db['ex'].get_users()]
    json_ret = []
    for user, owned in users:
        json_ret.append({
            F"{user}": [db['ex'].get_repo(x).to_json() for x in owned.split(", ")]
        })
    _ = db['ex'].to_json()
    return json.dumps(db['ex'].to_json(), indent=3)


def get_db():
    return db['ex']


if __name__ == "__main__":
    key = Fernet.generate_key()
    db['key'] = Fernet(key)
    socketio.run(app)

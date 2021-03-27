from flask import *
from database_manager import *
from cryptography.fernet import Fernet
import graphics_designer
from flask_socketio import SocketIO
import os
import numpy as np

app = Flask(__name__)
app.secret_key = b'_5y2L"\xea2L"F4Q8z\n\xec]\ny2L"F4Q8z\n\xec]]#y2L"F4Q8z\n\xec]/'
socketio = SocketIO(app)
db = {"ex": Database("databases/database")}


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


def draw_graph(to_highlight=None, reload_colors=True):
    session['image_size'] = graphics_designer.start_draw(session['current_repo'], session, to_highlight, reload_colors)
    # request.form['repos'] => current repo id
    make_image_map()
    # remove cashing
    reload_image()

#     current_b_id = data.get("commits", "branch", condition=f'id="{post_id}"')[0]
#     current_b = data.get("branches", "name", condition=f'id="{current_b_id}"')[0]
#     draw_graph(post_id, reload_colors=False)
#     session['head'] = data.get_repo(session['current_repo']).get_branch(current_b).head.get_id()


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

    # # # # # # # # # # # # # # # #
    #    User tries rendering     #
    # # # # # # # # # # # # # # # #

    if request.method == "POST":
        session['repos'] = [[x[0], x[1]] for x
                            in db['ex'].get("repos", "id, name, owners", first=False) if x[2].find(user) != -1]
        session['hightlighed'] = 0
        session['to_highlight'] = 0
        session['current_repo'] = 0
        session['current_commit_name'] = ''
        session['current_commit_desc'] = ''
        # # # # # # # # # # # # # # # #
        #   Highlighting something    #
        # # # # # # # # # # # # # # # #
        try:
            session['to_highlight'] = request.form['to_highlight']
            repo_id = db["ex"].get("commits", "repo", f'id="{session["to_highlight"]}"')[0]
            session['current_repo'] = db['ex'].get("repos", "name", condition=f'id="{repo_id}"')[0]
        except:
            pass
        x = session['to_highlight']
        if str(x) != "0":
            session['current_commit_name'] = db["ex"].get("commits", "commit_name", f'id="{x}"')[0]
            session['current_commit_desc'] = db["ex"].get("commits", "comment", f'id="{x}"')[0]

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
            repo = db['ex'].get('commits', 'repo', f'id={request.form["commit_man"]}')[0]

            db['ex'].get_repo(repo).get_branch(bran).create_commit(name, comment, session['user'], previous=request.form["commit_man"])
            flash(f"Succesfully commited {name}: {comment}")
            return render_template("repos.html")

        if session['current_repo'] == 0:
            try:
                session['current_repo'] = request.form['repos']
                if session['current_repo'] == '':
                    raise ValueError
            except Exception as e:
                print(e)
                flash("You need to select a repo first")
                return render_template("repos.html")
        draw_graph(to_highlight=session['to_highlight'], reload_colors=session['to_highlight']==0)
    else:
        graphics_designer.start_draw(0, session, erase=True)
        reload_image()
    # # # # # # # # # # # # # # # #
    #   Simply loading the page   #
    # # # # # # # # # # # # # # # #
    return render_template("repos.html")


def get_db():
    return db['ex']


if __name__ == "__main__":
    key = Fernet.generate_key()
    db['key'] = Fernet(key)
    socketio.run(app)

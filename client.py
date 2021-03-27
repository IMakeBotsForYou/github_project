from database_manager import *
from graphics_designer import *
from website_manager import *
#  comment, creator, previous=-1, first=False, next_commitx=-1
db = Database('databases/database')
# focused = db.get_repo(1).fork("Main","Guy")
db.remove("repos")
db.remove('branches')
db.remove("commits")
# # print(json.dumps(db.to_json(), indent=3))
db.create_repository("This project", "Dan, Guy, Dvir, Eran")
db.create_repository("some other repo", "Dan, Eran, Ron F")
#
r1 = db.get_repo(1)
r2 = db.get_repo(2)

r1_b = r1.get_branches()
r2_b = r2.get_branches()
# name, comment, creator, previous=-1, first=False, next_commitx=-1
r1_b[0].create_commit("First commit", "Starting database, dan.", "Dan")
r1_b[0].create_commit("Second commit", "Updated something small", "Dan")

r1.fork("Main", "Dan")
r1_b = r1.get_branches()
r1_b[0].create_commit("Bug add", "Added Herobrine", "Dvir")
r1_b[1].create_commit("Changed project", "Made dan throw away all his work!", "Eran")
r1_b[0].create_commit("Bug fix", "Removed Herobrine", "Dan")
r1_b[1].create_commit("pain", "Crying in the corner while starting anew", "Dan")
print(json.dumps(db.to_json(), indent=3))

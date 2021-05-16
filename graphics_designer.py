import cv2
import numpy as np
from json import load
import website_manager
import database_manager

all_data = {
    "cp_data": {
        "current palette": 0,
        "palette index": 1
    },
    "cl": {},
    "save_depths": {},
    "save_colors": {},
    "all_colours": {},
    "last_repo": 0,
    "branches": [],
    "size": [0, 0]
}
db_obj = None


def line(a, img, pt1, pt2, color, thickness):
    if str(a) == "1":
        cv2.line(img, pt1, pt2, color, thickness)
    else:
        dotted_line(img, pt1, pt2, color, thickness)


def dotted_line(img, pt1, pt2, color, thickness=5):
    on_dottiness = 2
    off_dottiness = 10
    on = True
    x1 = pt1[0]
    x2 = pt2[0]
    y1 = pt1[1]
    y2 = pt2[1]
    if y1 > y2:
        y1, y2 = y2, y1
    if x1 == x2:
        while y1 <= y2:
            if on:
                dottiness = on_dottiness
                cv2.line(img, (x1, y1), (x2, y1 + dottiness), color, thickness)
            dottiness = off_dottiness
            if y1 + dottiness >= y2:
                dottiness = y2 - y1 + 2
            y1 += dottiness
            on = not on

    if y1 == y2:
        while x1 <= x2:
            if on:
                dottiness = on_dottiness
                cv2.line(img, (x1, y1), (x1 + dottiness, y2), color, thickness)
            dottiness = off_dottiness
            if x1 + dottiness >= x2:
                dottiness = x2 - x1 + 2
            x1 += dottiness
            on = not on


def initialize_graphics():
    global db_obj, all_colours, all_data
    all_data['cl'] = [hex2rgb(a[1:]) for a in load(open("colors_palettes.json"))]
    all_colours = all_data['cl'].copy()
    db_obj = database_manager.my_db


def get_cl(counter):
    r = all_data['cl'][counter%6]
    return r


def calculate_size(bruh_repo, data):
    # noinspection PyUnresolvedReferences
    commits = db_obj.get_commits_info(bruh_repo)
    lenghts = [cv2.getTextSize(x[0], cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, thickness=2)[0][0] + x[1] * 100 + 70 for x
               in data]

    try:
        all_data["size"] = [len(commits) * 80 + 10, max(lenghts)]
    except:
        all_data["size"] = [len(commits) * 80 + 10, 10]


def hex2rgb(hex):
    return tuple(int(hex[i:i + 2], 16) for i in (0, 2, 4))


def get_com(all, value):
    for item in all:
        if str(item[0]) == str(value):
            return item


def start_draw(s, to_highlight=None, reload_colors=False, erase=False, force=False):
    global all_data
    if 'current_repo' in s:
        bruh_repo = s['current_repo']
    else:
        bruh_repo = 0
    if erase:
        image = np.zeros([1, 1, 3], dtype=np.uint8)
        image.fill(255)
        cv2.imwrite(f'./static/rendered_{s["user"]}_0.png', image)
        return 0, 0
    save_depths, save_colors, cl, all_colours = \
        all_data['save_depths'], all_data['save_colors'], all_data['cl'], all_data['all_colours']
    x = 0
    y = 0

    if not db_obj:
        initialize_graphics()
    user_name = s['user']
    s['file_name'] = "rendered_" + user_name
    # noinspection PyUnresolvedReferences
    commits = db_obj.get_commits_info(bruh_repo)
    # id, commit_name, comment, branch, next_commit, previous_commit, depth
    depths = {}
    b_colors = {}
    connections = {}
    dec = 0
    current_y = 50
    left_margin = 30
    branches = list(all_data['save_depths'].keys())
    # # # # # # # # # # # # # # # # # #
    # THIS PART INITIATES THE COLOURS #
    # # # # # # # # # # # # # # # # # #
    b_counter = 0
    for index, com in enumerate(commits):
        id, comment, _, bran, nex, pre, _, active = com
        if reload_colors or save_colors == {} or save_depths == {}:
            if bran not in b_colors:
                b_colors[bran] = get_cl(b_counter)
                b_counter += 1

                depths[bran] = dec
                branches.append(bran)
                branches = list(set(branches))
                dec += 1
        else:
            depths = save_depths.copy()
            b_colors = save_colors.copy()
    # item[1] == comment
    # item[2] == branch ids
    if x == 0 or y == 0 or force:
        calculate_size(bruh_repo,
                       data=[[item[1], depths[int(db_obj.get("commits", "branch", condition=f'id="{item[0]}"')[0])]] for
                             item in commits])
    x, y = all_data['size']
    image = np.zeros([x, y, 3], dtype=np.uint8)
    image.fill(255)

    # # # # # # # # # # # # # # # # # #
    # THIS PART INITIATES THE CIRCLES #
    # # # # # # # # # # # # # # # # # #
    for index, com in enumerate(commits):
        # id, commit_name, desc, branch, next_commit, previous_commit, depth
        id, comment, _, bran, nex, pre, depth, active = com
        cv2.rectangle(image, (0, index * 80 + 15), (x + 500, index * 80 + 60), (200, 200, 200), -1)
        if str(id) == str(to_highlight):
            cv2.rectangle(image, (0, index * 80 + 15), (x + 500, index * 80 + 60), (255, 211, 255), -1)
        distance = 100
        for bruh in branches:
            # is this our branch?
            if bruh == bran:
                data = (depth * distance + left_margin, current_y, b_colors[bran], comment, active)
                cv2.circle(image, (depth * distance + left_margin, current_y), radius=10, color=b_colors[bran],
                           thickness=-1)
                if str(pre) in connections and str(pre) != -1:
                    connections[str(pre)]["data"].append(data)
                    connections[str(id)] = {
                        "height": current_y,
                        "data": [data]
                    }
                else:
                    connections[str(id)] = {
                        "height": current_y,
                        "data": [data]
                    }
                db_obj.get_repo(bruh_repo).get_branch(bran).set_depth(depth)
                # we draw a circle on the commit's depth
        current_y += 80

    for index, com in enumerate(commits[::-1]):
        distance = 100
        # id, commit_name, desc, branch, next_commit, previous_commit, depth
        id, comment, _, bran, nex, pre, depth, active = com
        for bruh in branches:
            # is this our branch?
            if bruh == bran:
                # this time we already looped through everything, so
                # there's no need to check if something exists or not.
                # we will now loop backwards to connect nex instead
                # of prev.
                # current_data = (depth * distance + left_margin, current_y, b_colors[bran], comment)
                if str(nex) != "-1":
                    next_data = get_com(commits, nex)
                    i, c, _, b, n, p, d, active = next_data
                    latest_data = (d * distance + left_margin, connections[str(nex)]["height"], b_colors[b], c, active)
                    connections[str(id)]["data"].append(latest_data)
        current_y -= 80

    # # # # # # # # # # # # # # # # # # # # # # # # #
    # THIS PART DRAWS THE COMMIT'S CONNECTION LINES #
    # # # # # # # # # # # # # # # # # # # # # # # # #
    for id in connections:
        origin = connections[id]["data"][0]
        rest = connections[id]["data"][1:]
        for point in rest:
            x = point[0]  # x of point
            y = point[1]  # y of point
            c = point[2]  # point's color
            a = point[4]  # active or not
            if origin[0] == x:
                diff = 0
            else:
                diff = 30

            if diff == 0:
                line(a, image, (origin[0], origin[1]), (x, y), color=c, thickness=5)
            else:
                if origin[0] < x:
                    line(a, image, (origin[0], origin[1]), (x - diff, origin[1]), color=c, thickness=5)
                    line(a, image, (x, y), (x, origin[1] + diff), color=c, thickness=5)

                    cv2.circle(image, (origin[0], origin[1]), radius=10, color=origin[2], thickness=-1)
                    cv2.ellipse(image, (x - diff, origin[1] + 30), (30, 30), angle=0, startAngle=-90, endAngle=0,
                                color=c, thickness=5)

                else:
                    print(point[3], a)
                    line(a, image, (origin[0], origin[1]), (origin[0], y - diff), color=origin[2], thickness=5)
                    line(a, image, (x, y), (origin[0] - diff, y), color=origin[2], thickness=5)

                    cv2.circle(image, (origin[0], origin[1]), radius=10, color=origin[2], thickness=-1)
                    cv2.ellipse(image, (origin[0] - diff, y - diff), (30, 30), angle=0, startAngle=0, endAngle=90,
                                color=origin[2], thickness=5)
                    # this happens when something is
                    # merged back into a previous branch.

            # place border
            x = point[0]
            y = point[1]
            comment = point[3]

            font = cv2.FONT_HERSHEY_SIMPLEX
            bottom_left_corner_of_text = (x + 10, y - 10)
            font_scale = 1
            line_type = 2
            if origin[0] > x:
                cv2.putText(image, comment,
                            bottom_left_corner_of_text,
                            font,
                            font_scale,
                            (255, 255, 255),
                            5,
                            line_type)
    # # # # # # # # # # # # # # # # # # # # #
    # THIS PART DRAWS THE CONNECTIONS TABLE #
    # # # # # # # # # # # # # # # # # # # # #
    for id in connections:
        rest = connections[id]["data"]
        for point in rest:
            x, y, color, comment, _ = point
            font = cv2.FONT_HERSHEY_SIMPLEX
            bottom_left_corner_of_text = (x + 10, y - 10)
            fontScale = 1
            fontColor = color
            lineType = 2

            cv2.putText(image, comment,
                        bottom_left_corner_of_text,
                        font,
                        fontScale,
                        fontColor,
                        2,
                        lineType)
    # cv2.imshow("1", image)
    # cv2.waitKey(0)
    cv2.imwrite(f'./static/{s["file_name"]}_0.png', image)
    all_data['save_depths'] = depths.copy()
    all_data['save_colors'] = b_colors.copy()
    all_data['last_repo'] = bruh_repo
    return image.shape[1]

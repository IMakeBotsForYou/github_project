import cv2
import numpy as np
import json
import random

from website_manager import *
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


def initialize_graphics():
    global cl, db_obj, all_colours
    cl = json.load(open("colors_palettes.json"))
    for i, palette in enumerate(cl):
        for value in palette:
            a = cl[i][value][1:]
            cl[i][value] = tuple(int(a[i:i + 2], 16) for i in (0, 2, 4))

    all_colours = cl.copy()
    db_obj = get_db()


def get_cl():
    def gen_color():
        global all_data
        cp_data = all_data['cp_data']

        # if this palette is exhausted
        if cp_data['palette index'] == 7:
            # reset index, move to next palette
            cp_data['palette index'] = 1
            cp_data['current palette'] += 1
            if cp_data['current palette'] == 3:
                cp_data['current palette'] = 0

        val = cl[cp_data['current palette']][str(cp_data['palette index'])]
        cp_data['palette index'] += 1
        yield val

    return next(gen_color())


def calculate_size(bruh_repo, data):
    commits = db_obj.get_commits_info(bruh_repo)
    lenghts = [cv2.getTextSize(x[0], cv2.FONT_HERSHEY_SIMPLEX, fontScale=1, thickness=2)[0][0]+x[1]*100+70 for x in data]
    try:
        all_data["size"] = [len(commits) * 80, max(lenghts)]
    except:
        all_data["size"] = [len(commits) * 80+10, 10]


def hex2rgb(hex):
    return tuple(int(hex[i:i + 2], 16) for i in (0, 2, 4))


def start_draw(bruh_repo, s, to_highlight=None, reload_colors=False, erase=False):
    global all_data
    if erase:
        image = np.zeros([1, 1, 3], dtype=np.uint8)
        image.fill(255)
        cv2.imwrite(f'./static/{s["file_name"]}_0.png', image)
        return
    save_depths, save_colors, cl, all_colours =\
        all_data['save_depths'], all_data['save_colors'], all_data['cl'], all_data['all_colours']
    x = 0
    y = 0
    if bruh_repo == all_data['last_repo']:
       x = all_data['size'][0]
       y = all_data['size'][1]

    if not db_obj:
        initialize_graphics()
    user_name = s['user']
    s['file_name'] = "rendered_" + user_name
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
    for index, com in enumerate(commits):
        id, comment, _, bran, nex, pre, _ = com
        if reload_colors or save_colors == {} or save_depths == {}:
            if bran not in b_colors:
                b_colors[bran] = get_cl()
                depths[bran] = dec
                branches.append(bran)
                branches = list(set(branches))
                dec += 1
        else:
            depths = save_depths.copy()
            b_colors = save_colors.copy()
    # item[1] == comment
    # item[2] == branch ids
    if x == 0 or y == 0:
        calculate_size(bruh_repo, data=[[item[1], depths[int(db['ex'].get("commits", "branch", condition=f'id="{item[0]}"')[0])]] for item in commits])
    x, y = all_data['size']
    image = np.zeros([x, y, 3], dtype=np.uint8)
    image.fill(255)

    # # # # # # # # # # # # # # # # # #
    # THIS PART INITIATES THE CIRCLES #
    # # # # # # # # # # # # # # # # # #
    for index, com in enumerate(commits):
        # id, commit_name, desc, branch, next_commit, previous_commit, depth
        id, comment, _, bran, nex, pre, depth = com
        cv2.rectangle(image, (0, index * 80 + 15), (x+500, index * 80 + 60), (200, 200, 200), -1)
        if str(id) == str(to_highlight):
            cv2.rectangle(image, (0, index * 80 + 15), (x+500, index * 80 + 60), (255, 211, 255), -1)
        distance = 100
        for bruh in branches:
            # is this our branch?
            if bruh == bran:
                data = (depth * distance + left_margin, current_y, b_colors[bran], comment)
                cv2.circle(image, (depth * distance + left_margin, current_y), radius=10, color=b_colors[bran],
                           thickness=-1)
                if str(pre) in connections and str(pre) != -1:
                    connections[str(pre)].append(data)
                    connections[str(id)] = [data]
                else:
                    connections[str(id)] = [data]
                db['ex'].get_repo(bruh_repo).get_branch(bran).set_depth(depth)
                print(id, depth, db['ex'].get_repo(bruh_repo).get_branch(bran).depth)
        current_y += 80
        # we draw a circle on the commit's depth
    # # # # # # # # # # # # # # # # # # # # # # # # #
    # THIS PART DRAWS THE COMMIT'S CONNECTION LINES #
    # # # # # # # # # # # # # # # # # # # # # # # # #
    for id in connections:
        origin = connections[id][0]
        rest = connections[id][1:]
        for point in rest:
            x = point[0]
            y = point[1]
            c = point[2]
            if origin[0] == x:
                diff = 0
            else:
                diff = 30

            if diff == 0:
                cv2.line(image, (origin[0], origin[1]), (x, y), color=c, thickness=5)
            else:
                if origin[0] < x:
                    cv2.line(image, (origin[0], origin[1]), (x - diff, origin[1]), color=c, thickness=5)
                    cv2.line(image, (x, y), (x, origin[1] + diff), color=c, thickness=5)

                    cv2.circle(image, (origin[0], origin[1]), radius=10, color=origin[2], thickness=-1)
                    cv2.ellipse(image, (x-diff, origin[1]+30), (30, 30), angle=0, startAngle=-90, endAngle=0, color=c, thickness=5)

                else:
                    cv2.line(image, (origin[0], origin[1]), (origin[0], y-diff), color=origin[2], thickness=5)
                    cv2.line(image, (x, y), (origin[0]-diff, y), color=origin[2], thickness=5)

                    cv2.circle(image, (origin[0], origin[1]), radius=10, color=origin[2], thickness=-1)
                    cv2.ellipse(image, (origin[0] - diff, y-diff), (30, 30), angle=0, startAngle=0, endAngle=90,
                                color=origin[2], thickness=5)
            # place border
            x = point[0]
            y = point[1]
            comment = point[3]

            font = cv2.FONT_HERSHEY_SIMPLEX
            bottom_left_corner_of_text = (x + 10, y - 10)
            font_scale = 1
            line_type = 2
            # print(30 + dec*100-100 , x, cv2.getTextSize(comment, font, fontScale, lineType)[0][0])
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
        rest = connections[id]
        for point in rest:
            x, y, color, comment = point
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
    print(db['ex'].to_json())
    return image.shape[1]

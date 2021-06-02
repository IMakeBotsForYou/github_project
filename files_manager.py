import os
import shutil


def merge_dictionaries(files1, files2):
    for k in files1:
        current_commit_d_names = [x[0] for x in files1[k]]
        if k in files2:
            for f in files2[k]:
                if f[0] not in current_commit_d_names:
                    files1[k].append(f)
                else:
                    f[1].close()
                    print(f"Removing {os.path.join(os.getcwd(), f[1].name)}")
                    os.remove(os.path.join(os.getcwd(), f[1].name))

    for k in files2:
        if k not in files1:
            files1[k] = files2[k]

    return files1


def print_dir(dictionary):
    s = "\n"
    for sub in dictionary:
        s += f"\n{sub}:\n"
        for file in dictionary[sub]:
            s += f"\t{file[0]}\t{file[1].name}\n"
    s += "\n"
    print(s)


def make_archive(source, destination, disable_base=False):
    base = os.path.basename(destination)
    name = base.split('.')[0]
    format = base.split('.')[1]
    archive_from = source
    archive_to = os.path.basename(source.strip(os.sep))
    shutil.make_archive(name, format, base_dir=archive_from if not disable_base else None, root_dir=archive_to)
    shutil.move('%s.%s' % (name, format), destination)
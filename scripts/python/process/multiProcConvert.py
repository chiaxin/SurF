import os
import os.path
import sys
import subprocess
import multiprocessing

maketx = r'D:\Developments\Libraries\oiio\bin\maketx.exe'

def work(source, destination):
    p = subprocess.Popen('"%s" -oiio -o "%s" "%s"' % (
        maketx, source, destination
    ))
    p.communicate()


def main():
    workers = []
    sources      = sys.argv[0::2]
    destinations = sys.argv[1::2]
    for src, dest in zip(sources, destinations):
        workers.append(multiprocessing.Process(
            target = work,
            args=(src, dest)
        ))
    for worker in workers:
        worker.start()

if __name__ == "__main__":
    main()
    os.system("PAUSE")

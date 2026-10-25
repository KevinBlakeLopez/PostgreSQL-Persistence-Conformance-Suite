"""CHK-4 setup. Two steps, run around `docker run` (see README, "Running it").

  chk4_setup.py new-instance <dir>      writes <dir>/instance.json and <dir>/pg.env (both 0600): a random
                                        superuser password, app password and cluster_name token
  chk4_setup.py init-db <instance.json> creates the login role chk4_app (not a superuser), the database
                                        chk4 and its tables, through psql inside the container

The role's password is set with log_statement off, so it never reaches the server log.
"""
import json
import os
import secrets
import subprocess
import sys

CONTAINER = "ppcs-chk4-pg"
TABLES = """
create table chk4_item (id serial primary key, tag text not null unique);
create table chk4_parent (id int primary key);
create table chk4_child (
  id serial primary key,
  parent_id int not null references chk4_parent(id) deferrable initially deferred,
  tag text not null
);
"""


def new_instance(directory):
    instance = {"container": CONTAINER, "port": 55494, "cluster_name": f"chk4-{secrets.token_hex(8)}",
                "superuser_password": secrets.token_hex(16), "app_password": secrets.token_hex(16)}
    for name, body in (("instance.json", json.dumps(instance, indent=1) + "\n"),
                       ("pg.env", f"POSTGRES_PASSWORD={instance['superuser_password']}\n")):
        path = os.path.join(directory, name)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(body)
    print(instance["cluster_name"])


def psql(database, user, sql):
    subprocess.run(["docker", "exec", "-i", CONTAINER, "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
                    "-U", user, "-d", database], input=sql, text=True, check=True)


def init_db(instance_path):
    instance = json.load(open(instance_path))
    password = instance["app_password"]
    assert all(c in "0123456789abcdef" for c in password)
    psql("postgres", "postgres", "set log_statement = 'none';\n"
         f"create role chk4_app login password '{password}';\n"
         "reset log_statement;\ncreate database chk4 owner chk4_app;\n")
    psql("chk4", "chk4_app", TABLES)
    print("created chk4_app, database chk4, tables chk4_item, chk4_parent, chk4_child")


if __name__ == "__main__":
    {"new-instance": new_instance, "init-db": init_db}[sys.argv[1]](sys.argv[2])

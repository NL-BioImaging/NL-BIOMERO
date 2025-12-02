# Linux/Ubuntu Deployment

This guide provides detailed instructions for deploying NL-BIOMERO on
Ubuntu/Linux systems with SSL support.

\# NL‑BIOMERO (Ubuntu/Linux) 🚀

This guide covers deploying NL‑BIOMERO on **Ubuntu/Linux**, as always
tuned for FAIR imaging with BIOMERO, OMERO.forms, and other plugins.

---

\## 🧰 Prerequisites

- Ubuntu 18.04+ with Docker & Docker Compose
- OpenSSH client/server
- <span class="title-ref">chmod</span>,
  <span class="title-ref">iptables</span> or
  <span class="title-ref">ufw</span>
- Let's Encrypt SSL certificates (if using HTTPS)
- <span class="title-ref">.env</span> file pre-filled with your secure
  secrets (I'll get back to that later)

---

\## 🔧 Key Differences from Windows Docker Desktop

\### 1. PostgreSQL Image `` `yaml image: postgres:16-alpine ``\` Alpine
edition works more smoothly on Debian/Ubuntu hosts.

\### 2. Privileged Access Needed Add to omero-server, worker, and web
containers:

`` `yaml privileged: true # or security_opt:   - seccomp:unconfined ``\`

\### 3. SSH Permissions in biomero-worker On Linux, SSH folder is too
restrictive. Before launching containers:

`` `bash chmod -R 777 ~/.ssh docker compose up -d --build chmod -R 700 ~/.ssh ``\`
You could add this into a bash script so you don't forget. Or just keep
the .ssh folder open (but then you can't use it manually from the host).
Btw, you could move that folder to /opt/omero or something, it doesn't
need to be your user's home folder .ssh.

\### 4. Containerized Slurm Build **Note**: this is only about the
"fake" Slurm \<a
href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm"
target="\_blank" rel="noopener
noreferrer"\>NL-BIOMERO-Local-Slurm\</a\>. If you connect to an actual
HPC you won't have these issues of course. You will have other issues
probably ;)

Slurm doesn't build cleanly on Ubuntu. Build on Windows or CI, push to
Docker Hub, then use, e.g.:

`` `yaml services:   slurm-worker:     image: cellularimagingcf/slurm-docker-cluster-base:latest ``<span class="title-ref">
</span>`yaml services:   slurmctld:     image: cellularimagingcf/slurm-docker-cluster-slurmctld:latest`<span class="title-ref">
In short: use \<a
href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm/blob/master/docker-compose-from-dockerhub.yml"
target="\_blank" rel="noopener
noreferrer"\>\`docker-compose-from-dockerhub.yml</span>\</a\> for
deployment for local Slurm.

\### 5. Host Networking (host.docker.internal Replacement) **Note**:
this is only about the "fake" Slurm \<a
href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO-Local-Slurm"
target="\_blank" rel="noopener
noreferrer"\>NL-BIOMERO-Local-Slurm\</a\>. If you connect to an actual
HPC you won't have these issues of course. You will have other issues
probably ;)

Ubuntu doesn't support
<span class="title-ref">host.docker.internal</span>. Use Docker's
gateway IP (e.g. <span class="title-ref">172.17.0.1</span>). Also:

`` `bash sudo ufw allow 2222/tcp ``<span class="title-ref"> and forward
that port for Slurm SSH. Then your \`biomeroworker</span> can SSH into
your <span class="title-ref">slurmctld</span> via the host.

\### 6. Volume Permission Fixes "Permission denied" is common for mounts
on Linux. Fix interactively on the host side:

`` `bash chmod -R ... ``\`

Paths needing attention: - Shared data volumes (e.g. L-Drive in the
<span class="title-ref">web</span> folder) -
<span class="title-ref">slurm-config.ini</span> (in the
<span class="title-ref">web</span> folder) - SSH dir for
<span class="title-ref">10-mount-ssh.sh</span>
(<span class="title-ref">biomeroworker</span> startup)

Sometimes you might have permission issues inside a container;

`` `bash docker-compose exec <container> bash chmod ... ``\`

But, that is gone if you restart, so consider setting permissions in
Dockerfiles if stable. (e.g. by making a GitHub issue about it). I have
updated a few docker images for this purpose recently.

\### 7. Secrets & Metabase Setup Populate
<span class="title-ref">.env</span> with secure values:

`` `text POSTGRES_PASSWORD=... OMERO_ROOT_PASSWORD=... FORMS_MASTER_PASSWORD=... METABASE_USER=... METABASE_PASSWORD=... METABASE_SECRET_KEY=... ``\`

⚠️ <span class="title-ref">.env</span> is committed in the repo—override
before first run. *And don't commit those changes ;)*

For Metabase: 1. Log in to <span class="title-ref">localhost:3000</span>
with default credentials 2. Go to (admin) settings to reset your
password and to the database embed settigns for a new secret key 3.
Update <span class="title-ref">.env</span> and redeploy

\### 8. HTTPS via Nginx Reverse Proxy To get SSL / HTTPS, you need to
add a reverse proxy server like NGINX to reroute your server's traffic
and check against SSL certificates.

You could add this nginx service in Docker Compose:

`` `yaml nginx:   image: nginx:alpine   networks:     - omero   ports:     - "4080:4080"  # OMERO HTTP     - "4443:4443"  # OMERO HTTPS     - "3000:3000"  # Metabase HTTP     - "3443:3443"  # Metabase HTTPS   volumes:     - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro     - /etc/letsencrypt/:/etc/letsencrypt:ro ``\`

🔐 Don't expose OMERO or Metabase ports directly—route traffic through
nginx.

This is an alternative to directly forwarding the 4080 and 3000 ports
from the OMERO.web/Metabase services to your host system. Adapt the
<span class="title-ref">nginx.conf</span> to fit your scenario (like the
server url). *Hint: you can forward ports 80 and 443 to 4080 and 4443 on
your host to catch all normal http(s) traffic to your server URL.*

\### 9. Persistent Logs You probably want persistent logfiles.

Add volume mounts for logs to map them to your host system:

`` `yaml services:   omero-web:     volumes:       - ./logs/omero-web:/opt/omero/web/OMERO.web/var/log ``\`

This removes the need for <span class="title-ref">docker-compose exec
...</span> to read logs, and keeps historic logs around after you
redeploy the container.

---

\## ✅ Quick Start (Ubuntu)

`` `bash git clone https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO.git /opt/omero/NL-BIOMERO  # Prepare .env with secure values nano /opt/omero/.env  # Setup SSL # Ensure you have SSL certs first at /etc/letsencrypt/ nano /opt/omero/nginx/nginx.conf  # Setup SSH mkdir /opt/omero/.ssh cp /opt/omero/ssh.config.ubuntu.example /opt/omero/.ssh/config touch /opt/omero/.ssh/known_hosts # Copy, or make, SSH keys to that same folder # e.g. ssh-keygen -t rsa  # Setup some permissions chmod -R 777 /opt/omero/.ssh chmod -R 777 /opt/omero/NL-BIOMERO/web/L-Drive chmod -R 777 /opt/omero/NL-BIOMERO/web/slurm-config.ini  docker-compose -f /opt/omero/docker-compose-for-ubuntu-with-SSL.yml up -d --build docker-compose -f /opt/omero/docker-compose-for-ubuntu-with-SSL.yml logs -f  # Change metabase secrets at :3000 / :3443 and update .env # restart  docker-compose -f /opt/omero/docker-compose-for-ubuntu-with-SSL.yml down docker-compose -f /opt/omero/docker-compose-for-ubuntu-with-SSL.yml up -d --build ``\`

👉 Ensure your firewall allows ports: **4080**, **4443**, **3000**,
**3443**, and **2222**.

---

\## 🛠️ Troubleshooting Tips

Symptom \| Resolution \|

[\|---------\|](##SUBST##|---------|)------------\| \| "Permission
denied" (SSH) \| Use <span class="title-ref">chmod -R 777 ~/.ssh</span>
before booting \| \| Web login/password issues \| Make sure
<span class="title-ref">.env</span> is set, and handle Metabase
first-login flow \| \| Slurm SSH failure \| Verify Docker gateway IP and
open port 2222 \| \| SSL certificate issues \| Confirm cert paths and
reload nginx \|

---

\## 🧠 Lessons Learned

- **Permissions make or break Linux deployments**—pre-fix if possible
- <span class="title-ref">host.docker.internal</span> is unavailable:
  use dynamic gateway IP
- **Slurm is brittle**—better to pre-build and host container images
- **Nginx proxy handles HTTPS**, hides internal ports
- **Probably mount logs**—no more chasing with
  <span class="title-ref">exec</span> &
  <span class="title-ref">tail</span>

---

\## 📋 TL;DR

- Use <span class="title-ref">postgres:16-alpine</span>
- Add <span class="title-ref">privileged</span>/\`unconfined\` seccomp
- <span class="title-ref">chmod 777</span> SSH and writable mounts
- Deploy Slurm via pre-built images
- Use Docker gateway IP and open 2222
- Manage secrets via <span class="title-ref">.env</span>, treat Metabase
  manually
- Layer nginx proxy & mount SSL directories
- Persist logs via volume mounts

---

\## 🔗 Additional Resources

- \<a href="https://docs.docker.com/compose/" target="\_blank"
  rel="noopener noreferrer"\>Docker Compose Documentation\</a\>
- \<a href="https://certbot.eff.org/instructions?ws=nginx&os=ubuntu"
  target="\_blank" rel="noopener noreferrer"\>Let's Encrypt Ubuntu
  Guide\</a\>
- \<a href="https://omero.readthedocs.io/" target="\_blank"
  rel="noopener noreferrer"\>OMERO Documentation\</a\>
- \<a
  href="https://github.com/Cellular-Imaging-Amsterdam-UMC/NL-BIOMERO"
  target="\_blank" rel="noopener noreferrer"\>NL-BIOMERO GitHub\</a\>

If you run into any issues anyway, feel free to make an image.sc post or
a GitHub issue for it; you will probably help other people with the same
issues!

Happy imaging! 🔬✨

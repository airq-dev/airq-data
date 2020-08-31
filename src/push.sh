set -e

DB_FILE=airq.db
CWD=`pwd`

if [ ! -d "/home/ec2-user/airq-data/src/.venv" ]; then 
    echo "Creating virtual environment...\n"
    python3 -m venv /home/ec2-user/airq-data/src/.venv
fi

echo "Ensuring requirements are up to date...\n"
source .venv/bin/activate
python3 -m pip install -r /home/ec2-user/airq-data/src/requirements.txt

echo "Building the database...\n"
python3 /home/ec2-user/airq-data/src/build.py

timestamp=$(date +%s)
rm -rf /tmp/airq
tmpdir="/tmp/airq/build-$timestamp"
mkdir -p $tmpdir
cd $tmpdir

eval `ssh-agent -s`
ssh-add /home/ec2-user/.ssh/id_rsa

git clone -v git@github.com:airq-dev/airq.git
cd airq
git branch -D purpleair_sync || true
git checkout -b purpleair_sync
cp "$CWD/airq.db" app/airq/providers/purpleair.db
git add -A
git commit -m "Updating purpleair database"
git push -f origin purpleair_sync

#SBATCH -D /tmp
#SBATCH -J demo
#SBATCH --mem 4G
#SBATCH -c 1

echo "$(date) hello from $(hostname)" >> /work/example_job.txt
sleep 32

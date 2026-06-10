#!/bin/bash
#SBATCH --job-name=conversion
#SBATCH --array=1-1
#SBATCH -n 1
#SBATCH -N 1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32GB
#SBATCH --time=02:00:00

echo "Job Parameters:"
echo "CONFIG_PATH: $CONFIG_PATH"
echo "DATA_PATH: $DATA_PATH"
echo "CONVERSION_PATH: $CONVERSION_PATH"
echo "CONVERTER_IMAGE: $CONVERTER_IMAGE"

module load singularity || true

file_to_convert=$(awk -v ArrayTaskID=$SLURM_ARRAY_TASK_ID '$1==ArrayTaskID { $1=""; print substr($0,2) }' "$CONFIG_PATH")
echo "Processing task $SLURM_ARRAY_TASK_ID: $file_to_convert"

if [ -e "$file_to_convert" ]; then
    echo "Starting conversion for task $SLURM_ARRAY_TASK_ID..."
    if singularity run $CONVERSION_PATH/$CONVERTER_IMAGE "$file_to_convert"; then
        rm -rf "$file_to_convert"
        echo "Task $SLURM_ARRAY_TASK_ID completed successfully."
    else
        echo "ERROR: Conversion failed for task $SLURM_ARRAY_TASK_ID. Input file NOT deleted."
        exit 1
    fi
else
    echo "No corresponding input file for task $SLURM_ARRAY_TASK_ID."
    exit 1
fi

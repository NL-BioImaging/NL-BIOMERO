nl_biomero_verify_outputs() {
    if [ -z "${DATA_PATH:-}" ]; then
        return 0
    fi

    output_dir="$DATA_PATH/data/out"
    if [ ! -d "$output_dir" ]; then
        echo "ERROR: Workflow output directory does not exist: $output_dir" >&2
        return 2
    fi

    if [ -z "$(find "$output_dir" -mindepth 1 -print -quit)" ]; then
        echo "ERROR: Workflow completed without producing files in $output_dir" >&2
        return 2
    fi
}

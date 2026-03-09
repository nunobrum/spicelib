from spicelib.log.ltsteps import LTSpiceLogReader

def main():
    log_path = "./examples/testfiles/dc_no_step.log"
    LTSpiceLogReader(log_path)
    print("Parsed successfully")

if __name__ == "__main__":
    main()

import os
import sys
import subprocess
from dotenv import load_dotenv

load_dotenv()

# Automatically configure JAVA_HOME for PySpark (Prefer OpenJDK 17 LTS)
JAVA_17_HOME = r"C:\Program Files\Tableau\Tableau 2026.2\bin\jre"
JAVA_21_HOME = r"C:\Program Files\Android\Android Studio\jbr"

if os.path.exists(JAVA_17_HOME):
    os.environ["JAVA_HOME"] = JAVA_17_HOME
    os.environ["PATH"] = os.path.join(JAVA_17_HOME, "bin") + os.path.pathsep + os.environ.get("PATH", "")
elif os.path.exists(JAVA_21_HOME):
    os.environ["JAVA_HOME"] = JAVA_21_HOME
    os.environ["PATH"] = os.path.join(JAVA_21_HOME, "bin") + os.path.pathsep + os.environ.get("PATH", "")

# Configure HADOOP_HOME & winutils for PySpark Windows compatibility
winutils_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".winutils"))
bin_dir = os.path.join(winutils_dir, "bin")
winutils_exe = os.path.join(bin_dir, "winutils.exe")

os.makedirs(bin_dir, exist_ok=True)
if not os.path.exists(winutils_exe):
    try:
        ps_cmd = f"Add-Type -TypeDefinition 'using System; public class Program {{ public static void Main(string[] args) {{}} }}' -OutputAssembly '{winutils_exe}' -OutputType ConsoleApplication"
        subprocess.run(["powershell", "-Command", ps_cmd], check=True, capture_output=True)
    except Exception:
        pass

os.environ["HADOOP_HOME"] = winutils_dir
os.environ["PATH"] = bin_dir + os.path.pathsep + os.environ.get("PATH", "")

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
db_path = os.path.join(base_dir, "urbantransit.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")

RAW_DATA_DIR = os.getenv("RAW_DATA_DIR", os.path.join(base_dir, "raw_data"))
PARQUET_DATA_DIR = os.getenv("PARQUET_DATA_DIR", os.path.join(base_dir, "parquet_data"))
PROCESSED_DATA_DIR = os.getenv("PROCESSED_DATA_DIR", os.path.join(base_dir, "processed_data"))
MODELS_DIR = os.getenv("MODELS_DIR", os.path.join(base_dir, "models"))

# Configurable Operational & Performance Thresholds
OVERCROWDING_THRESHOLD_PCT = 90      # Occupancy % that triggers overcrowded flag
UNDERUTILIZED_THRESHOLD_PCT = 30     # Occupancy % that triggers underutilized flag
DELAY_MINOR_MIN = 5                  # Delay duration thresholds in minutes
DELAY_MODERATE_MIN = 15
DELAY_MAJOR_MIN = 30
DELAY_SEVERE_MIN = 60
FORECAST_DEFAULT_HORIZON_DAYS = 7
OCCUPANCY_SAMPLE_FRACTION = 0.12

def get_spark_session(app_name="UrbanTransit_App"):
    from pyspark.sql import SparkSession
    spark = SparkSession.builder \
        .appName(app_name) \
        .master("local[*]") \
        .config("spark.sql.parquet.enableVectorizedReader", "false") \
        .config("spark.hadoop.fs.file.impl", "org.apache.hadoop.fs.RawLocalFileSystem") \
        .config("spark.hadoop.io.native.lib.available", "false") \
        .getOrCreate()
    return spark


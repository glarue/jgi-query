# jgi-query
A command-line tool for querying and downloading from the [Joint Genome Institute (JGI)](http://genome.jgi-psf.org/) online database. Useful for accessing JGI data from command-line-only resources such as remote servers, or as a lightweight alternative to JGI's other GUI-based download tools.

### Dependencies
- A [user account with JGI](http://contacts.jgi-psf.org/registration/new) (free)
- [cURL](http://curl.haxx.se/), required by the JGI download API
- [Python](https://www.python.org/downloads/) 2.7.x

### Installation
1. Download `jgi-query.py`
2. Ensure that you're running the correct version of Python with `python --version`. If this reports Python 3.x, run the script using `python2` instead of `python`
3. From the command line, run the script with the command `python jgi-query.py` to show usage information and further instructions

### Author notes
This is a somewhat better-commented (emphasis on "somewhat") version of a script I wrote for grabbing various datasets from a headless Linux server. For a lot of my lab's bioinformatics work, we don't store/manipulate data on our local computers, and I was not able to find a good tool that allowed for convenient queries of the JGI database without additional software.

JGI also no longer allows simple downloading of many of their datasets (via `wget`, for example), which is another reason behind the creation of this script.

I highly encourage anyone with more advanced Python skills (read: almost everyone) to fork and submit pull requests. I am happy if this can help anyone access data more quickly!

PROJECT_DIR = "../test-spider/"
CACHE_DIR = ".scrapy/"
HTTPCACHE_DIR = 'httpcache_gzip'

# This script runs a set of spiders using the default compression backend.
# After running the set of spiders once, it checks their output files and
# records the size. It then swaps out the compression backend being used
# and runs the same spider again. Finally the size of the files
# the spiders create is checked again and recorded. Once this is done
# the size of the files created by the spiders during the first run
# is compared to the size of the files during the second run. The
# folowing data is then written to a file called "compresion_test.txt"
# -- The name of file output by the spider
# -- A short description of the test
# -- The size of the file under default compression
# -- The size of the file after using the new compression
# -- Percent improvment in disk usage between the two backends

import scrapy
import os
from os.path import join, getsize

from twisted.internet import reactor, defer
from scrapy.crawler import CrawlerRunner
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings

# To handle outputting the size of files generated by each spider
# perhaps we can use some utility functions that each spider can call
# on the file it creates after doing its work

# We will probably need a data structure to keep track of the
# the info we will write to "compression_test.txt" file that we will
# use to keep track of how much space each file uses
# I suggest a python dictionary or whatever it has


# PLACE UTILITY FUNCTIONS HERE

def getPathSize(start_path = '.'):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(start_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size



# END UTILITY FUNCTIONS


# ARRANGE TEST SPIDERS HERE
# Any spider used to test the compression backend should have its
# code placed here. 

# Fanfic Test Spider
# The purpose of this spider is to to test our compression algorith
# against a data set that should provide a high degree of variablity
# (the test in a bit of fanfiction. This should give us a small delta
 
class FanficSpider(scrapy.Spider):
    name = "fanfic_test"
    allowed_domains = ["fanfiction.net"]
    start_urls = [
        "https://www.fanfiction.net/s/11490724/1/Snowflake-s-Passage-First-story-Scary-Things",
        "https://www.fanfiction.net/s/11498367/1/Left-Turn"]

    def parse(self, response):
        filename = 'fanfic_test.html'
        with open(filename, 'wb') as f:
            f.write(response.body)

class OtherTestSpider(scrapy.Spider):
    name = "other_spider"
    allowed_domain = ["fanfiction.net"]
    start_urls = [
        "https://www.fanfiction.net/s/11490724/1/Snowflake-s-Passage-First-story-Scary-Things",
        "https://www.fanfiction.net/s/11498367/1/Left-Turn"]

    def parse(self, response):
        filename = 'other_test.html'
        with open(filename, 'wb') as f:
            f.write(response.body)

class XkcdSpider(scrapy.Spider):
    name = "xkcd"
    allowed_domains = ["10.10.10.10"]
    start_urls = (
        'http://10.10.10.10/',
    )

    def parse(self, response):
        # Safe if Xpath is empty, extract handles it.
        prev_link = response.xpath('//*[@id="middleContainer"]/ul[1]/li[2]/a/@href').extract()
        if prev_link:
            url = response.urljoin(prev_link[0])
            yield scrapy.Request(url, callback=self.parse)

# END TEST SPIDERS

# Do some initial set up
configure_logging()
runner = CrawlerRunner()

@defer.inlineCallbacks
def crawl():
    # Yield the result of calling runner.crawl on your spider here
    yield runner.crawl(FanficSpider)
    yield runner.crawl(OtherTestSpider)
    yield runner.crawl(XkcdSpider)
    reactor.stop()

#crawl()


fullCacheDir = PROJECT_DIR + CACHE_DIR + HTTPCACHE_DIR
print os.path.join(fullCacheDir)
print ("Calculating the size of a cache directory '%s'." % fullCacheDir)
print "This may take a while..."
sizeInBytes = getPathSize(fullCacheDir)
print("Total size for '%s': %.2f MB" % ( fullCacheDir, sizeInBytes / 2**20))


reactor.run()

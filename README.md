# RSU_tax_helper
To help declare your RSUs for Criteo.

Easily adaptable for other companies. IT even tries to optimize a little your declaration.

How to use
=========

* Install [Jupyter notebook](https://jupyter.org/install)
* in a repo, using the comand line (cmd) run git clone https://github.com/nchrys/RSU_tax_computer.git.
* From the root of this repo run `jupyter notebook` in the command line
* Select the file `RSU_tax_computer.ipynb` in your browser
* You might need to install python dependencies if you have runtime errors (eg: `pip install pandas`)
* Put your own information for all your vesting (with the vesting date, and the number of shares) and all your sold share with again the date and the amount sold (in shares, not euro).
* Then just run the notebook and you will have all information to report in the cells at the end.


## Using Binder:
(easy for non jupyter common users)

1 -follow this link (takes some time to load sorry) https://mybinder.org/v2/gh/nchrys/RSU_tax_computer/HEAD?labpath=RSU_tax_computer.ipynb

2 - Then fill your data in cell [4], and launch kernel restart and run all in the kernel menu at the top.

Disclaimer: I am no accountant, I did this to help, I hope there are no mistake, but If there is, first I am sorry, but I am not responsible

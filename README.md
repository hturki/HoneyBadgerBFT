# HoneyBadgerBFT
The Honey Badger of BFT Protocols


<img width=200 src="http://i.imgur.com/wqzdYl4.png"/>

Most fault tolerant protocols (including RAFT, PBFT, Zyzzyva, Q/U) don't guarantee good performance when there are Byzantine faults.
Even the so-called "robust" BFT protocols (like UpRight, RBFT, Prime, Spinning, and Stellar) have various hard-coded timeout parameters, and can only guarantee performance when the network behaves approximately as expected - hence they are best suited to well-controlled settings like corporate data centers.

HoneyBadgerBFT is fault tolerance for the wild wild wide-area-network. HoneyBadger nodes can even stay hidden behind anonymizing relays like Tor, and the purely-asynchronous protocol will make progress at whatever rate the network supports.

### License
This is released under the CRAPL academic license. See ./CRAPL-LICENSE.txt
Other licenses may be issued at the authors' discretion.

### Making this work with HyperLedger

On an Amazon CentOS 7 instance:

sudo yum groupinstall "Development Tools" -y
sudo yum install epel-release -y 
sudo yum install screen git tmux wget libtool-ltdl-devel python-pip python-devel gmp-devel openssl-devel glibc-static gmp-static libstdc++-static gnutls-devel libgcrypt-devel -y

wget https://redirector.gvt1.com/edgedl/go/go1.9.2.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.9.2.linux-amd64.tar.gz
sudo chown -R centos /usr/local/go

echo "export PATH=$PATH:/usr/local/go/bin" >>  ~/.bashrc
echo "export FABRIC_CFG_PATH=/usr/local/go/src/github.com/hyperledger/fabric/sampleconfig" >>  ~/.bashrc

source ~/.bashrc

mkdir -p /usr/local/go/src/github.com/hyperledger/
cd /usr/local/go/src/github.com/hyperledger/
git clone https://github.com/hturki/fabric
cd fabric/orderer
go build
cd sample_clients/broadcast_msg
go build
cd ../deliver_stdout/
go build
sudo mkdir /var/hyperledger
sudo chown -R centos /var/hyperledger

cd ~/
wget https://crypto.stanford.edu/pbc/files/pbc-0.5.14.tar.gz
tar -xvf pbc-0.5.14.tar.gz
cd pbc-0.5.14 && ./configure && sudo make && sudo make install

sudo pip install PySocks pycrypto ecdsa zfec gipc

cd ~/
git clone https://github.com/JHUISI/charm.git
cd charm && git checkout 2.7-dev && ./configure.sh && sudo python setup.py install

cd ~/
git clone https://github.com/hturki/HoneyBadgerBFT
cd HoneyBadgerBFT
mkdir dkg
cd dkg
git clone https://github.com/amiller/distributed-keygen DKG_0.8.0
cd DKG_0.8.0/PBC/
sudo make clean && sudo make
cd ../src
sudo make clean && sudo make

And then on separate screens:

Start up HoneyBadger BFT:

cd ~/HoneyBadgerBFT
export LD_LIBRARY_PATH=/usr/local/lib
export LIBRARY_PATH=/usr/local/lib
sh launch-4.sh

Start up the orderer:

cd /usr/local/go/src/github.com/hyperledger/fabric/orderer
./orderer

Broadcast a message:

cd /usr/local/go/src/github.com/hyperledger/fabric/orderer/sample_clients/broadcast_msg/
./broadcast_msg

View the output of the chain in human readable form:

cd /usr/local/go/src/github.com/hyperledger/fabric/orderer/sample_clients/deliver_stdout/
./deliver_stdout


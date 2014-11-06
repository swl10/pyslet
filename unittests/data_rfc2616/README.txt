WARNING: this directory contains an insecure private key and self-signed
certificate used for testing purposes only.  Never use these files for a
real application!

Inspired by the succinct recipe published here:
http://carlo-hamalainen.net/blog/2013/1/24/python-ssl-socket-echo-test-with-self-signed-certificate

openssl genrsa -des3 -out server.orig.key 2048
openssl rsa -in server.orig.key -out server.key
openssl req -new -key server.key -out server.csr
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt

Typical usage:

    import pyslet.http.server as http
    s = http.Server(8443, keyfile='server.key', certfile='server.crt')
    s.handle_request()

For info, the output of the following command is printed below:
openssl x509 -in server.crt -noout -text

Certificate:
    Data:
        Version: 1 (0x0)
        Serial Number:
            fa:0d:76:1d:fd:b6:cf:34
        Signature Algorithm: sha1WithRSAEncryption
        Issuer: C=GB, ST=Cambridgeshire, L=Cambridge, O=Pyslet, OU=Developer, CN=localhost/emailAddress=no-reply@pyslet.org
        Validity
            Not Before: Nov  6 08:13:14 2014 GMT
            Not After : Oct 13 08:13:14 2114 GMT
        Subject: C=GB, ST=Cambridgeshire, L=Cambridge, O=Pyslet, OU=Developer, CN=localhost/emailAddress=no-reply@pyslet.org
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
            RSA Public Key: (2048 bit)
                Modulus (2048 bit):
                    00:b4:4b:bc:3f:a5:79:5f:f4:24:9e:1c:ba:d2:b4:
                    21:d4:01:c6:66:85:f9:cb:3f:43:af:ee:8c:62:30:
                    ba:1c:3d:a3:0e:2b:61:f7:91:bd:07:b8:7f:0e:86:
                    29:db:84:25:1d:aa:fd:3a:cf:7d:fc:06:d2:22:18:
                    38:7e:f3:bd:8d:d9:5b:61:ab:ef:15:5b:0e:e9:8f:
                    71:d1:f2:72:a3:6a:f6:f6:4f:66:41:5f:25:1d:c1:
                    a4:02:eb:b6:b1:28:93:14:26:f1:f7:56:1a:a8:c1:
                    23:ce:25:9c:da:f9:e2:43:20:9f:3c:f6:0a:50:47:
                    ab:20:5f:5b:4c:a8:fc:b0:9d:35:5f:a7:93:16:f7:
                    f7:64:36:39:1f:ec:ac:1b:15:79:3b:d7:2e:b9:e1:
                    fb:67:65:46:57:5b:ad:09:18:e0:ea:65:86:dd:35:
                    af:cc:fa:5a:88:e0:12:cf:7a:a0:6c:cc:6c:2a:0a:
                    c1:70:f7:56:24:cb:35:87:ba:dd:36:73:5b:07:fd:
                    43:f5:5e:4d:9e:a0:52:5b:4e:2a:fa:cd:24:b0:92:
                    ed:42:14:c3:b1:78:e4:68:50:f3:54:7b:9e:48:5a:
                    12:83:bf:61:e4:09:e1:b9:0f:d8:e5:72:9f:25:9c:
                    39:2e:ef:fc:d9:03:3f:7b:40:c4:01:11:d3:9d:11:
                    42:c1
                Exponent: 65537 (0x10001)
    Signature Algorithm: sha1WithRSAEncryption
        25:dd:fd:cc:79:23:bc:c3:0c:c9:29:a7:25:9d:d5:d1:60:09:
        5a:60:e8:b6:33:4e:b5:2d:68:c0:f1:89:4e:0b:e9:4e:74:9f:
        69:86:ae:d5:03:53:62:a6:30:db:b6:82:4f:5b:1f:2f:87:f4:
        3c:a1:eb:27:2b:05:33:6e:81:e0:8c:a2:94:a8:f3:0a:33:c3:
        e9:09:70:e1:dc:8c:af:40:11:45:53:00:2c:ef:6f:d3:72:e4:
        ae:71:e9:9a:ad:ed:87:ef:f5:3a:31:8e:b7:80:3c:e9:ca:f2:
        f2:a4:b5:59:59:b5:13:75:03:27:8e:3d:43:ab:c6:a6:e9:35:
        15:b1:1c:88:a7:aa:e9:4f:3a:43:a4:fa:fa:ef:4b:9c:25:d8:
        f3:20:a7:fc:87:5b:d4:43:37:6c:2c:33:43:a7:3e:d1:f1:cd:
        b8:50:fb:f1:56:39:c8:c7:ae:3b:99:ac:19:af:b9:b3:95:73:
        17:db:52:ec:14:f9:4d:b9:15:6b:27:ae:e0:d1:3b:d9:92:d0:
        1a:3c:ab:57:1b:54:b3:b2:e6:70:2d:e8:c8:f2:43:ff:bf:29:
        91:80:62:ef:e8:c6:95:f6:b2:40:c3:d2:9d:d6:5d:3a:2e:fc:
        92:85:f7:cc:93:77:94:f2:ef:1a:98:ac:79:74:41:94:ba:e6:
        a5:5d:12:b0

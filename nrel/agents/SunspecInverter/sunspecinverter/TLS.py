from OpenSSL.crypto import load_certificate, FILETYPE_ASN1
#Ref to https://github.com/pyca/pyopenssl/tree/master/examples
class Certificate_Mgmt:
    '''
    IEEE 8.11
    Device Certificate is issued by manifacturer at the time of creation [Not implemented yet] [Future to be one of the inverter models]
    Self-Signed Client Certificate will be used as generated below
    '''

    def __init__(self):
        pass

    def gen_keys(self, type, bits):
        """
        Create a public/private key pair.

        Arguments: type - Key type, must be one of TYPE_RSA and TYPE_DSA
                bits - Number of bits to use in the key
        Returns:   The public/private key pair in a PKey object
        """
        pkey = crypto.PKey()
        pkey.generate_key(type, bits)
        return pkey
        pass

    def req_cert(self, pkey, digest="sha256", **name):
        """
        Create a certificate request.

        Arguments: pkey   - The key to associate with the request
                digest - Digestion method to use for signing, default is sha256
                **name - The name of the subject of the request, possible
                            arguments are:
                            C     - Country name
                            ST    - State or province name
                            L     - Locality name
                            O     - Organization name
                            OU    - Organizational unit name
                            CN    - Common name
                            emailAddress - E-mail address
        Returns:   The certificate request in an X509Req object
        """
        req = crypto.X509Req()
        subj = req.get_subject()
        for key, value in name.items():
            setattr(subj, key, value)
        req.set_pubkey(pkey)
        req.sign(pkey, digest)
        return req

    def create_CA(self, req, issuerCertKey, serial, validityPeriod,
                      digest="sha256"):
        '''
        Generate a certificate given a certificate request.

        Arguments: req        - Certificate request to use
                issuerCert - The certificate of the issuer
                issuerKey  - The private key of the issuer
                serial     - Serial number for the certificate
                notBefore  - Timestamp (relative to now) when the certificate
                                starts being valid
                notAfter   - Timestamp (relative to now) when the certificate
                                stops being valid
                digest     - Digest method to use for signing, default is sha256
        Returns:   The signed certificate in an X509 object
        '''
        issuerCert, issuerKey = issuerCertKey
        notBefore, notAfter = validityPeriod
        cert = crypto.X509()
        cert.set_serial_number(serial)
        cert.gmtime_adj_notBefore(notBefore)
        cert.gmtime_adj_notAfter(notAfter)
        cert.set_issuer(issuerCert.get_subject())
        cert.set_subject(req.get_subject())
        cert.set_pubkey(req.get_pubkey())
        cert.sign(issuerKey, digest)
        return cert
        


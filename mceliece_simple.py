import numpy as np

def gf2_mat_mul(A, B):
    """Multiplication de matrices sur GF(2)."""
    return np.matmul(A, B) % 2

def gf2_mat_inv(A):
    """
    Inverse une matrice carrée sur GF(2) en utilisant l'élimination de Gauss-Jordan.
    Retourne l'inverse ou lève une erreur si singulière.
    """
    n = A.shape[0]
    # Matrice augmentée [A | I]
    aug = np.hstack((A, np.eye(n, dtype=int)))
    
    # Élimination de Gauss-Jordan
    for i in range(n):
        # Recherche du pivot
        pivot = -1
        for j in range(i, n):
            if aug[j, i] == 1:
                pivot = j
                break
        
        if pivot == -1:
            raise ValueError("La matrice est singulière (non inversible).")
            
        # Échange des lignes
        if pivot != i:
            aug[[i, pivot]] = aug[[pivot, i]]
            
        # Élimination des autres lignes
        for j in range(n):
            if i != j and aug[j, i] == 1:
                aug[j] = (aug[j] + aug[i]) % 2
                
    # Extraction de l'inverse (partie droite de la matrice augmentée)
    return aug[:, n:]

def gf2_rank(A):
    """Calcule le rang d'une matrice sur GF(2)"""
    # Version simplifiée par élimination gaussienne
    B = A.copy()
    rows, cols = B.shape
    rank = 0
    for c in range(cols):
        if rank >= rows: break
        pivot = -1
        for r in range(rank, rows):
            if B[r, c] == 1:
                pivot = r
                break
        if pivot != -1:
            B[[rank, pivot]] = B[[pivot, rank]]
            for r in range(rows):
                if r != rank and B[r, c] == 1:
                    B[r] = (B[r] + B[rank]) % 2
            rank += 1
    return rank


# --- Paramètres du Code de Hamming (7,4) ---

# Matrice Génératrice G (systématique)
# p1 p2 p3 p4 | d1 d2 d3
# G = [I | P]
G_std = np.array([
    [1, 0, 0, 0, 0, 1, 1],
    [0, 1, 0, 0, 1, 0, 1],
    [0, 0, 1, 0, 1, 1, 0],
    [0, 0, 0, 1, 1, 1, 1]
], dtype=int)

# Matrice de Parité H correspondante
# H = [P.T | I]
H_std = np.array([
    [0, 0, 0, 1, 1, 1, 1],
    [0, 1, 1, 0, 0, 1, 1],
    [1, 0, 1, 0, 1, 0, 1]
], dtype=int)


def generate_keys(fixed_S=None, fixed_perm=None):
    """Génère les clés publique et privée pour McEliece."""
    
    print("--- Génération des Clés ---")
    
    if fixed_S is not None:
        S = np.array(fixed_S, dtype=int)
        try:
            S_inv = gf2_mat_inv(S)
        except ValueError:
            raise ValueError("La matrice S fournie n'est pas inversible.")
    else:
        while True:
            # 1. Générer une matrice inversible S (4x4) aléatoire
            # Utilisation d'une graine aléatoire pour la reproductibilité si besoin, mais ici purement aléatoire
            S_cand = np.random.randint(0, 2, (4, 4))
            
            try:
                S_inv = gf2_mat_inv(S_cand)
                S = S_cand
                break
            except ValueError:
                continue # Réessayer si singulière

    print(f"1. Matrice brouilleuse S (4x4) :\n{S}")

    # 2. Générer une matrice de permutation P (7x7)
    n = 7
    P = np.zeros((n, n), dtype=int)
    
    if fixed_perm is not None:
        perm = np.array(fixed_perm, dtype=int)
        if len(perm) != n or len(set(perm)) != n or np.min(perm) != 0 or np.max(perm) != n-1:
             raise ValueError(f"La permutation fournie doit contenir tous les entiers de 0 à {n-1}.")
    else:
        perm = np.random.permutation(n)

    for i, p in enumerate(perm):
        P[i, p] = 1
        
    print(f"2. Matrice de Permutation P (7x7) basée sur {perm} :\n{P}")
    
    # 3. Calculer la clé publique G_pub = S * G * P
    # Note : G_std est la matrice du code (privée)
    
    # S * G
    SG = gf2_mat_mul(S, G_std)
    # (S * G) * P
    G_pub = gf2_mat_mul(SG, P)
    
    print(f"3. Matrice Clé Publique (G_pub) :\n{G_pub}")
    
    public_key = (G_pub, 1) # t=1 capacité d'erreur
    private_key = (S, S_inv, P, G_std, H_std)
    
    return public_key, private_key

def encrypt(message, public_key):
    """
    Chiffrement de McEliece : c = m * G_pub + z
    message: vecteur de 4 bits
    """
    G_pub, t = public_key
    m = np.array(message, dtype=int)
    
    # c_temp = m * G_pub
    c_temp = gf2_mat_mul(m, G_pub)
    
    # Génération vecteur erreur z de poids t=1
    n = G_pub.shape[1]
    z = np.zeros(n, dtype=int)
    err_idx = 3
    z[err_idx] = 1
    
    # c = c_temp + z
    ciphertext = (c_temp + z) % 2
    
    print("\n--- Chiffrement ---")
    print(f"Message clair m : {m}")
    print(f"Erreur ajoutée z (pos {err_idx}) : {z}")
    print(f"Texte chiffré c : {ciphertext}")
    
    return ciphertext

def decode_hamming(y, H):
    """Décodage par syndrome pour Hamming (7,4)."""
    # Syndrome s = H * y^T
    s = gf2_mat_mul(H, y.T) % 2
    
    if np.all(s == 0):
        return y # Pas d'erreur
        
    # Trouver la colonne de H qui correspond au syndrome
    # (dans cette construction, la colonne i de H indique une erreur au bit i)
    for i in range(H.shape[1]):
        if np.array_equal(H[:, i], s):
            # Correction de l'erreur
            y_corr = y.copy()
            y_corr[i] = (y_corr[i] + 1) % 2
            return y_corr
            
    # Si le syndrome ne correspond à aucune colonne (plus d'1 erreur), échec
    return None 

def decrypt(ciphertext, private_key):
    """
    Déchiffrement :
    1. c' = c * P^-1
    2. m' = Decoder(c')
    3. m = m' * S^-1
    """
    S, S_inv, P, G, H = private_key
    
    print("\n--- Déchiffrement ---")
    
    # 1. Inverser la permutation
    # Pour une matrice de permutation, P^-1 = P.T
    P_inv = P.T
    c_hat = gf2_mat_mul(ciphertext, P_inv)
    print(f"1. Vecteur dé-permuté (c * P^-1) : {c_hat}")
    
    # 2. Décoder le code linéaire
    m_hat_code = decode_hamming(c_hat, H)
    
    if m_hat_code is None:
        raise ValueError("Erreur de décodage : trop d'erreurs ou erreur non corrigible.")
        
    print(f"2. Vecteur corrigé (dans le code C) : {m_hat_code}")
    
    # Extraction du message 'u' tel que u * G = m_hat_code
    # Puisque G est sous forme systématique [I | P], les 4 premiers bits sont le message
    # (Attention : il faut être sûr que G est systématique sur les 4 premiers bits)
    u = m_hat_code[:4]
    
    # ici 'u' correspond à m * S
    m_S = u
    print(f"   Message extrait du code (m * S) : {m_S}")
    
    # 3. Inverser la matrice S
    # m = (m * S) * S^-1
    m_dec = gf2_mat_mul(m_S, S_inv)
    
    print(f"3. Message final déchiffré (m) : {m_dec}")
    
    return m_dec

if __name__ == "__main__":
    # Test
    ma_matrice_S = [
    [1, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1]]
    
    ma_perm = [0, 3, 6, 1, 5, 2, 4]

    pub_k, priv_k = generate_keys(fixed_S=ma_matrice_S, fixed_perm=ma_perm)
    
    # Message à envoyer
    msg = [1, 0, 1, 1]
    
    encrypted = encrypt(msg, pub_k)
    decrypted = decrypt(encrypted, priv_k)
    
    if np.array_equal(msg, decrypted):
        print("\n=> SUCCÈS : Le message déchiffré correspond !")
    else:
        print("\n=> ÉCHEC : Erreur de déchiffrement.")

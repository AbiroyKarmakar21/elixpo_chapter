
document.getElementById("signin_with_github").addEventListener("click", () => {
    var provider = new firebase.auth.GithubAuthProvider();

    firebase.auth().signInWithPopup(provider)
    .then(function(result) {
        var token = result.credential.accessToken;
        var user = result.user;

        var docRef = db.collection("users").doc(user.displayName);

        docRef.get().then((doc) => { // gets the whole data against the entered email address
            if (doc.exists) {
                tileFlash();
                if(doc.data().isDev == "DEV")
                    {
                        notify("Login Successful!");
                        localStorage.setItem("ElixpoAIUser", usernameSignIn);
                        setTimeout(() => {
                            location.replace("elixpoArtGenerator.html");
                        }, 2000);
                    }
                    else 
                    {
                        LoginError("Access Denied!");
                        RemovetileFlash();
                    }
            } else {
           
                tileFlash();
                db.collection('users').doc(user.displayName.toLowerCase()).set({
                    username: user.displayName.toLowerCase(),
                    email: user.email,
                    uid: user.uid,
                    displayName: user.displayName,
                    dateCreated: date,
                    isDev: "NotDev",
                    provider: "Github",
                    token : token,
                    plan : "lix",
                    coins : 1000000,
                    user_logo: user.photoURL,
                }).then(() => {
                    RemovetileFlash();
                    localStorage.setItem("ElixpoAIUser", user.displayName);
                    location.replace("elixpoArtGenerator.html");
                })
                .catch((err) => {
                    RemovetileFlash();
                    console.error("Error adding document: ", err);
                    RegisterError("Some Error Occured!");
                });
            }
        }).catch((err) => {
            RemovetileFlash();
            console.error("Error getting document:", err);
        });
    })
    
    .catch((err) => {
        console.error("Error during signInWithPopup:", err.message);
        tileFlash();
        if(err.message == "An account already exists with the same email address but different sign-in credentials. Sign in using a provider associated with this email address.")
        {
            RegisterError("Email Associated with Different Account/Service");
        }
        else 
        {
            RegisterError("Some Error Occured!");
        }
        RemovetileFlash();
    });
    RemovetileFlash();
});

function RegisterError(err) {
    document.getElementById("RegisterError").innerText = err;
    setTimeout(() => {
        document.getElementById("RegisterError").innerText = "";
    }, 3500);
}

function tileFlash() {

    const tiles = document.querySelectorAll('.tile');
    const baseDelay = 90; // Base delay in milliseconds
    const delayIncrement = 50; // Increment delay for each subsequent tile

    tiles.forEach((tile, index) => {
        const delay = baseDelay + (index * delayIncrement);
        setTimeout(() => {
            tile.classList.add('flash');
        }, delay);
    });

}

function RemovetileFlash() {
    const tiles = document.querySelectorAll('.tile');
    tiles.forEach((tile) => {
        tile.classList.remove('flash');
    });
}
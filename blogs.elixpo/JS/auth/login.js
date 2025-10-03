const otpInputs = document.querySelectorAll('#otpLabel input[type="text"]');
let token = "bljY0G";
let emailResp = "ayushbhatt633@gmail.com";
let userInpEmail = "ayushbhatt633@gmail.com";
const githubClientID = "Ov23li51zbnVuh5pmkbK"

window.onload = function() {
    checkExistingAuth();
    showElement('inputLabel');
    hideElement('otpLabel');
    checkURLParamsLogin();

};



async function checkExistingAuth() {
    console.log("🔍 Checking existing authentication...");
    console.log("🍪 Current browser cookies:", document.cookie);
    
    const res = await fetch("http://localhost:5000/api/checkAuth", {
        credentials: 'include',
    });

    if (res && res.status === 200) {
        const data = await res.json();
        console.log("🔍 Auth check successful:", data);
        
        if (data.user) {
            console.log("👤 User email:", data.user.email);
            console.log("🔑 User token:", data.user.token);
            console.log("🆔 User UID:", data.user.uid); 
            console.log("📋 Full user object:", data.user);
        }
        
    } else {
        console.log("❌ Auth check failed or user not authenticated");
    }
}

// hideElement and showElement functions are now in helperFunction.js

function checkURLParamsLogin() {
    const urlParams = new URLSearchParams(window.location.search);
    const tokenParam = urlParams.get('token');
    const operation = urlParams.get('operation');
    const state = urlParams.get('state');
    const code = urlParams.get('code');
    let callback = urlParams.get('callback');
    
    console.log("URL Parameters:", { tokenParam, operation, state, callback, code });
    
    if (callback === 'true' && operation === 'login' && state === 'elixpo-blogs' && tokenParam) {
        verifyLoginOTP(tokenParam, null, operation, state, otp=null, callback=true);
    }
    else if(operation != null && operation != "login" || (state != null && !state.startsWith("elixpo-blogs"))) {
        showNotification("Invalid login request. Please try logging in again.");
        resetLoginForm();
    }
}

document.getElementById("loginBtn").addEventListener("click", function() {
    showNotification("Sending OTP via email...");
    disableElement('loginBtn');
    userInpEmail = document.getElementById("email").value;
    var verifiedEmail = safeInputEmail(userInpEmail);
    if (!verifiedEmail) {
        showNotification("Ooppss crack!! Please enter a valid email address buddy.");
        enableElement('loginBtn');
        resetLoginForm();
        return;
    }
    
    const rememberMe = document.getElementById("rememberMe") ? document.getElementById("rememberMe").checked : false;
    
    const response = fetch('http://localhost:5000/api/loginRequest?email=' + encodeURIComponent(verifiedEmail) + '&remember=' + rememberMe, {
        method: 'GET',
        credentials: 'include', 
        headers: {
            'Content-Type': 'application/json'
        },
    });
    response.then(res => res.json()).then(data => {
        if (data.error) {
            showNotification(data.error); 
        } else {
            let msg = data.message || "OTP sent! Please check your email.";
            [emailResp, token] = (data.data || data.message).split(',');
            sessionStorage.setItem('email', emailResp);
            sessionStorage.setItem('token', token);
            sessionStorage.setItem('rememberMe', rememberMe);
            showNotification(msg);
            hideElement('inputLabel');
            showElement('otpLabel');
        }
    }).catch(() => {
        showNotification("Network error. Please check your connection and try again.");
    });
});

otpInputs.forEach((input, idx) => {
    input.addEventListener('input', function () {
        this.value = this.value.replace(/[^0-9]/g, '');
        if (this.value.length === 1 && idx < otpInputs.length - 1) {
            otpInputs[idx + 1].focus();
        }
        if ([...otpInputs].every(inp => inp.value.length === 1)) {
            verifyLoginOTP(token, emailResp, null, null, [...otpInputs].map(inp => inp.value).join(''), false);
        }
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && this.value === '' && idx > 0) {
            otpInputs[idx - 1].focus();
        }
    });
});

function resetLoginForm() {
    otpInputs.forEach(input => input.value = '');
    document.getElementById("email").value = '';
    hideElement('otpLabel');
    showElement('inputLabel');
    sessionStorage.removeItem('email');
    sessionStorage.removeItem('token');
    sessionStorage.removeItem('rememberMe');
    token = null;
    emailResp = null;
    userInpEmail = null;
}

function verifyLoginOTP(token, emailResp=null, operation=null, state=null, otp=null, callback=false) {
    console.log("Verifying OTP with:", { token, emailResp, operation, state, otp, callback });
    showNotification("Verifying OTP, just a moment...");
    const rememberMe = sessionStorage.getItem('rememberMe') === 'true';
    if (callback === true) {
        disableElement('loginBtn');
        showNotification("Verifying OTP, just a moment...");
        hideElement('inputLabel');
        hideElement('otpLabel');
        console.log("checking from the callback")
        const response = fetch(`http://localhost:5000/api/verifyLoginOTP?token=${encodeURIComponent(token)}&email=${encodeURIComponent(emailResp)}&time=${encodeURIComponent(Date.now())}&state=${encodeURIComponent(state)}&operation=${encodeURIComponent(operation)}&callback=${true}&remember=${rememberMe}`, 
        { method: 'GET',
            credentials: 'include', 
            headers: {
            'Content-Type': 'application/json'
        },
         })
        response.then((res) => {
            console.log("🍪 OTP verification response headers:", [...res.headers.entries()]);
            const setCookieHeader = res.headers.get('set-cookie');
            if (setCookieHeader) {
                console.log("🍪 Set-Cookie header received:", setCookieHeader);
                document.cookie = setCookieHeader;
            } else {
                console.log("⚠️ No Set-Cookie header received in response.");
            }
            return res.json();
        }).then((data) => {
            console.log("🍪 After OTP verification - cookies:", document.cookie);
            if (data.status) {
                showNotification(data.message || "🎉 OTP verified! Welcome!");
                setTimeout(() => {
                    console.log("🍪 Cookies after delay:", document.cookie);
                }, 500);
                setTimeout(() => {
                    // console.log("Verified and stored cookie" + document.cookie);
                    redirectTo("src/feed")
                }, 1500);
            } else {
                showNotification(data.error || "❗ OTP verification failed. Please try again.");
                resetLoginForm();
            }
        }).catch(() => {
            showNotification("🔥 Network error during OTP verification.");
            resetLoginForm();
        });
    return;
    }

    else if (!token || emailResp != userInpEmail) {
        showNotification("❗ Oops! OTP verification failed. Please try logging in again.");
        resetLoginForm();
        return;
    }
    else 
    {
        const response = fetch('http://localhost:5000/api/verifyLoginOTP?otp=' + encodeURIComponent(otp) + '&token=' + encodeURIComponent(token) + '&email=' + encodeURIComponent(emailResp) + '&time=' + encodeURIComponent(Date.now()) + '&remember=' + rememberMe, 
        { method: 'GET',
            credentials: 'include', 
            headers: {
            'Content-Type': 'application/json'
        },
         })
    response.then((res) => {
            console.log("🍪 OTP verification response headers:", [...res.headers.entries()]);
            const setCookieHeader = res.headers.get('Set-Cookie');
            if (setCookieHeader) {
                console.log("🍪 Set-Cookie header received:", setCookieHeader);
                document.cookie = setCookieHeader;
            } else {
                console.log("⚠️ No Set-Cookie header received in response.");
            }
            return res.json();
        }).then((data) => {
            console.log("🍪 After OTP verification - cookies:", document.cookie);
            if (data.status) {
                showNotification(data.message || "🎉 OTP verified! Welcome!");
                setTimeout(() => {
                    console.log("🍪 Cookies after delay:", document.cookie);
                }, 1500);
                setTimeout(() => {
                    redirectTo("src/feed")
                }, 1500);
            } else {
                showNotification(data.error || "❗ OTP verification failed. Please try again.");
                resetLoginForm();
            }
        }).catch(() => {
            showNotification("🔥 Network error during OTP verification.");
            resetLoginForm();
        });
    return;
    }
}

function logout() {
    fetch('http://localhost:5000/api/logout', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        showNotification(data.message || "✅ Logged out successfully!");
        setTimeout(() => {
            window.location.href = '/login';
        }, 1500);
    })
    .catch(() => {
        showNotification("🔥 Error during logout.");
    });
}

// showNotification function is now in helperFunction.js

function safeInputEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        return;
    }
    const sqlInjectionPattern = /('|--|;|\/\*|\*\/|xp_|exec|union|select|insert|delete|update|drop|alter|create|truncate|script|<|>)/i;
    if (sqlInjectionPattern.test(email)) {
        return;
    }
    console.log("Logging in user:", email);
    return email;
}

// disableElement and enableElement functions are now in helperFunction.js


document.getElementById("loginGithub").addEventListener("click", function () {
  loginWithGitHub();
});

document.getElementById("loginGoogle").addEventListener("click", function() {
    loginWithGoogle();
});


function loginWithGoogle() {
    showNotification("Redirecting to Google for authentication...");
    disableElement('loginGoogle');
    
    const googleClientId = "796328864956-hn8dcs3t1i3kui6qd8pvhhblj5c8c66k.apps.googleusercontent.com";
    
    // Google OAuth URL
    const googleAuthUrl =
    `https://accounts.google.com/o/oauth2/v2/auth?` +
    `client_id=${googleClientId}` +
    `&redirect_uri=${encodeURIComponent("http://localhost:3000/src/auth/callback")}` +
    `&response_type=code` +
    `&scope=${encodeURIComponent("openid email profile")}` +
    `&state=elixpo-blogs-google` +
    `&access_type=offline` +
    `&prompt=consent`;

    const popup = window.open(googleAuthUrl, 'googleAuth', 'width=500,height=600,scrollbars=yes,resizable=yes');

    const checkClosed = setInterval(() => {
        if (popup.closed) {
            clearInterval(checkClosed);
            enableElement('loginGoogle');
            window.location.reload();
        }
    }, 1000);
}

function loginWithGitHub() {
  showNotification("Redirecting to GitHub for authentication...");
  disableElement("loginGithub");
  const githubAuthUrl =
    `https://github.com/login/oauth/authorize?client_id=${githubClientID}` +
    `&redirect_uri=${encodeURIComponent("http://localhost:3000/src/auth/callback")}` +
    `&scope=user:email&state=elixpo-blogs-github`;

  window.location.href = githubAuthUrl;
}


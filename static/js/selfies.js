var url_params = window.location.href;
window.noheader = true;

var action_bar_visible = false;
var loading_more = false;
var photos_initially_loaded = false;
var photo_data_base64 = null;
var streamRef = null;

var fake_modal = document.getElementById('fake_modal');
var a_post = document.querySelector('a.post');






var showModal = function(item) {
    // console.log('photo: ', item);
    hide_modal('webcam_modal')
    
    var overlay = document.createElement('div');
    overlay.className = 'overlay invisible';

    var gutter = document.createElement('div');
    gutter.className = 'gutter';

    var modal = document.createElement('div');
    modal.className = 'modal photo';
    
    var img = document.createElement('div');
    img.className = 'photo';
    img.style.background = 'white url('+item.photo_url_s3.replace('http:', 'https:')+') center center no-repeat';
    img.style.backgroundSize = 'auto 100%';
    modal.appendChild(img);

    var tweet = document.createElement('div');
    if (!item.share) {
        tweet.className = 'tweet';
    
        var avatar = document.createElement('a');
        avatar.className = 'avatar';
        avatar.href = item.original_url;
        avatar.target = '_blank';
        var avimg = document.createElement('img');
        avimg.src = item.user_avatar_s3;
        avatar.appendChild(avimg);
        tweet.appendChild(avatar);

        var username = document.createElement('a');
        username.href = item.original_url;
        username.target = "_blank";
        username.textContent = item.username + ":";
        tweet.appendChild(username);

        if (item.caption.length <= 140)
            var caption = item.caption;
        else
            var caption = item.caption.substr(0, 140) + '…';

        var text = document.createElement('span');
        text.src = item.user_avatar_s3;
        text.textContent = ' ' + caption;
        tweet.appendChild(text);
    } else {
        tweet.className = 'tweet share';
        var shareLink = SITE_URL+'/photo/'+item.permalink_slug;

        if (item.landing) {
            var span = document.createElement('span');
            span.innerHTML = 'Get to the polls! Text <strong>VOTE</strong> to <a href="sms://384387">384-387</a> or visit <a href="https://www.hello.vote/" target="_blank">Hello.Vote</a> for polling place directions and reminders!';
            tweet.appendChild(span);

            var post = document.createElement('a');
            post.className = 'share join';
            post.href = '#';
            post.textContent = 'I voted!';
            post.addEventListener('click', function(e) {
                e.preventDefault();
                close_modal();
                participate();
            }, false);
            tweet.appendChild(post);
        } else {
            var span = document.createElement('span');
            span.textContent = 'Share your letter to the FCC and encourage your friends to do it to!';
            tweet.appendChild(span);
        }

        var fb = document.createElement('a');
        fb.className = 'share fb';
        fb.href = '#';
        fb.textContent = 'Share';
        fb.addEventListener('click', function(e) {
            e.preventDefault();
            window.open('https://www.facebook.com/sharer/sharer.php?u='+encodeURIComponent(shareLink));
        }, false);
        tweet.appendChild(fb);

        var tw = document.createElement('a');
        tw.className = 'share tw';
        tw.href = '#';
        tw.textContent = 'Tweet';
        tw.addEventListener('click', function(e) {
            e.preventDefault();
            window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(TWEET_TEXT+' '+(item.photo_display_url ? item.photo_display_url : item.photo_url_s3)));
        }, false);
        tweet.appendChild(tw);

        if (getMobileOperatingSystem() == 'Android' || getMobileOperatingSystem() == 'iOS') {
            var sms = document.createElement('a');
            sms.className = 'share sms';
            sms.href = '#';
            sms.textContent = 'Text';
            sms.addEventListener('click', function(e) {
                e.preventDefault();
                shareSMS(shareLink);
            }, false);
            tweet.appendChild(sms);
        }
    }

    var close = document.createElement('a');
    close.href = '#';
    close.className = 'close';
    close.addEventListener('click', function(e) {
        e.preventDefault();
        close_modal();
    }, false);
    modal.appendChild(close);


    modal.appendChild(tweet);
    
    gutter.appendChild(modal);
    overlay.appendChild(gutter);
    document.body.appendChild(overlay);

    var close_modal = function() {
        overlay.className = 'overlay invisible';
        setTimeout(function() {
            document.body.removeChild(overlay);
        }, 400);
    }

    gutter.addEventListener('click', function(e) {
        if (e.target == gutter)
            close_modal();
    }, false);

    overlay.style.display = 'block';
    setTimeout(function() { overlay.className = 'overlay'; }, 50);
}




var promotedPage = 0;
var promotedPerPage = 60;
var fillSize = 60;
var finishedPromoted = false;






var show_modal = function(el) {
    var overlay = document.getElementById(el);
    overlay.style.display = 'block';
    setTimeout(function() { overlay.className = 'overlay'; }, 30);
}

var hide_modal = function(el) {
    var overlay = document.getElementById(el);
    overlay.className = 'overlay invisible';
    setTimeout(function() { overlay.style.display = 'none'; }, 400);
}

var bind_hide = function(el) {
    document.querySelector('#'+el+' .close.lite').addEventListener(
        'click', function(e) {
            e.preventDefault();
            hide_modal(el);
        }, false
    );
}

var close_modals = ['webcam_modal'];

for (var i=0; i<close_modals.length; i++)
    bind_hide(close_modals[i]);

var open_webcam_modal = function() {
    show_modal("webcam_modal");
    setTimeout(function() {
        initialize_webcam();
    }, 300);
};

var initialize_webcam = function() {
    // The width and height of the captured photo. We will set the
    // width to the value defined here, but the height will be
    // calculated based on the aspect ratio of the input stream.

    var width = 640;    // We will scale the photo width to this
    var height = 0;     // This will be computed based on the input stream

    // |streaming| indicates whether or not we're currently streaming
    // video from the camera. Obviously, we start at false.

    var streaming = false;

    // The various HTML elements we need to configure or control. These
    // will be set by the startup() function.

    var video = null;
    var canvas = null;
    var startbutton = null;
    var photoData = null;

    var startup = function() {
        video = document.getElementById('video');
        canvas = document.getElementById('canvas');
        startbutton = document.getElementById('startbutton');
        reset_photo_elements();

        navigator.getMedia = ( navigator.getUserMedia ||
            navigator.webkitGetUserMedia ||
            navigator.mozGetUserMedia ||
            navigator.msGetUserMedia);

        navigator.getMedia(
            {
                video: true,
                audio: false
            },
            function(stream) {
                streamRef = stream;
                if (navigator.mozGetUserMedia) {
                    video.mozSrcObject = stream;
                } else {
                    var vendorURL = window.URL || window.webkitURL;
                    video.src = vendorURL.createObjectURL(stream);
                }
                video.play();
            },
            function(err) {
                console.log("An error occured! " + err);
            }
        );

        video.addEventListener('canplay', function(ev){
            if (!streaming) {
                height = video.videoHeight / (video.videoWidth/width);

                // Firefox currently has a bug where the height can't be read from
                // the video, so we will make assumptions if this happens.

                if (isNaN(height)) {
                    height = width / (4/3);
                }

                video.setAttribute('width', width);
                video.setAttribute('height', height);
                canvas.setAttribute('width', width);
                canvas.setAttribute('height', height);
                streaming = true;
                document.getElementById('frame').style.display = 'block';

                document.querySelector('#webcam_modal .close.lite').addEventListener(
                    'click',
                    function(e) {
                        clearphoto();
                        if (streamRef) {
                            stopStream();
                        }
                    },
                    false
                );
            }
        }, false);

        startbutton.addEventListener('click', function(ev){
            takepicture();
            ev.preventDefault();
        }, false);

        clearphoto();
    }

    // Fill the photo with an indication that none has been
    // captured.

    var clearphoto = function() {
        var context = canvas.getContext('2d');
        context.fillStyle = "#AAA";
        context.fillRect(0, 0, canvas.width, canvas.height);

        var data = canvas.toDataURL('image/png');
        photo.setAttribute('src', data);
    }

    // Capture a photo by fetching the current contents of the video
    // and drawing it into a canvas, then converting that to a PNG
    // format data URL. By drawing it on an offscreen canvas and then
    // drawing that to the screen, we can change its size and/or apply
    // other changes before drawing it.

    var takepicture = function() {
        if (!streaming)
            return startup();

        var context = canvas.getContext('2d');
        if (width && height) {
            canvas.width = width;
            canvas.height = height;
            context.drawImage(video, 0, 0, width, height);

            document.getElementById('shutter').play();
            document.getElementById('flash').style.display = 'block';
            setTimeout(function() {
                document.getElementById('flash').style.display = 'none';
            }, 2500);

            photoData = canvas.toDataURL('image/png');
            photo_data_base64 = photoData.replace(/^data:image\/(png|jpg|jpeg);base64,/, "");
            photo.setAttribute('src', photoData);

            video.style.display = 'none';
            photo.style.display = 'block';

            setTimeout(function() {
                document.getElementById('startbutton').style.display = 'none';
                document.getElementById('use').style.display = 'inline-block';
                document.getElementById('retake').style.display = 'inline-block';
            }, 125);
        } else {
            clearphoto();
        }
    }

    startup();
};

var stopStream = function() {
    if (streamRef.stop) streamRef.stop();
    else if (streamRef.getTracks) streamRef.getTracks()[0].stop();
    streamRef = null;
}

var reset_photo_elements = function() {
    document.getElementById('startbutton').style.display = 'inline-block';
    document.getElementById('use').style.display = 'none';
    document.getElementById('retake').style.display = 'none';
    document.getElementById('video').style.display = 'block';
    document.getElementById('photo').style.display = 'none';
}
var submit_photo_data = function() {
    $.ajax({
        type: 'POST',
        url: '/base64',
        data: { 'img_data': photo_data_base64 },
        success: function(data){
            hide_loader();
            
            data = JSON.parse(data);
            if (!data || data.error)
                return alert('Could not save that photo. Please try again!');

            console.log('return json: ', data);
            data.share = true;
            showModal(data);
        },
        error: function() {
            hide_loader();
            alert('Could not save that photo. Please try again!');
        }
    });
}
var participate = function() {
    if (getMobileOperatingSystem() == 'Android' || getMobileOperatingSystem() == 'iOS')
        document.getElementById('file').click();
    else
        open_webcam_modal();
}

var postButtons = document.querySelectorAll('a.post')

for (var i=0; i<postButtons.length; i++) {
    postButtons[i].addEventListener('click', function(e) {
        e.preventDefault();
        participate();
    }, false);
}

document.querySelector('#file').addEventListener('change', function(e) {
    var file = document.querySelector('#file').files[0];
    console.log('file: ', file);
    var reader = new FileReader();
    reader.onload = function(e) {
        photo_data_base64 = e.target.result.replace(/^data:image\/(png|jpg|jpeg);base64,/, "");
        show_loader();
        submit_photo_data();
    }
    reader.readAsDataURL(file);
}, false);

document.getElementById('retake').addEventListener('click', function(e) {
    e.preventDefault();
    reset_photo_elements();
}, false);

document.getElementById('use').addEventListener('click', function(e) {
    e.preventDefault();
    show_loader();
    if (streamRef) {
        stopStream();
    }
    submit_photo_data('webcam_modal');
}, false);


var show_loader = function() {
    var loader = document.getElementById('loader');
    loader.style.display = 'block';
    setTimeout(function() { loader.className = ''; }, 30);
}

var hide_loader = function() {
    var loader = document.getElementById('loader');
    loader.className = 'invisible';
    setTimeout(function() { loader.style.display = 'none'; }, 400);
}

if (LOAD_PHOTO) {
    $.ajax('/photo/'+LOAD_PHOTO+'?return=json', {
        success: function(data) {
            data = JSON.parse(data);
            if (!data || data.error)
                return;

            // console.log('return json: ', data);
            data.share = true;
            data.landing = true;
            showModal(data);
        }
    });
}

if (document.getElementById('user_agent'))
    document.getElementById('user_agent').textContent = navigator.userAgent || navigator.vendor || window.opera;

// console.log('getMobileOperatingSystem: ', getMobileOperatingSystem())

/**
 * Determine the mobile operating system.
 * This function returns one of 'iOS', 'Android', 'Windows Phone', or 'unknown'.
 *
 * @returns {String}
 */
function getMobileOperatingSystem() {
    var userAgent = navigator.userAgent || navigator.vendor || window.opera;

    // Windows Phone must come first because its UA also contains "Android"
    if (/windows phone/i.test(userAgent)) {
        return "Windows Phone";
    }

    if (/android/i.test(userAgent)) {
        return "Android";
    }

    // iOS detection from: http://stackoverflow.com/a/9039885/177710
    if (/iPad|iPhone|iPod/.test(userAgent) && !window.MSStream) {
        return "iOS";
    }

    return "unknown";
}

var shareSMS = function(shareLink) {

    if (getMobileOperatingSystem() == 'Android')
        window.open('sms:?body='+encodeURIComponent('I voted! '+shareLink));
    else
        window.open('sms:&body='+encodeURIComponent('I voted! '+shareLink));
}

const socket = io();



let auctionEndTime = auctionStartTime + auctionDuration;



function updateTimer() {

const now = Math.floor(Date.now() / 1000);

if (now < auctionStartTime) {

const remainingStart = auctionStartTime - now;

const minutes = Math.floor(remainingStart / 60).toString().padStart(2, '0');

const seconds = Math.floor(remainingStart % 60).toString().padStart(2, '0');

document.getElementById('timer').innerText = `Aukcja startuje za: ${minutes}:${seconds}`;

document.querySelector('button').disabled = true;

} else {

const remaining = auctionEndTime - now;

if (remaining <= 0) {

document.getElementById('timer').innerText = 'Aukcja zakończona';

document.querySelector('button').disabled = true;

} else {

const minutes = Math.floor(remaining / 60).toString().padStart(2, '0');

const seconds = Math.floor(remaining % 60).toString().padStart(2, '0');

document.getElementById('timer').innerText = `Pozostały czas: ${minutes}:${seconds}`;

document.querySelector('button').disabled = false;

}

}

}

setInterval(updateTimer, 1000);

updateTimer();



function sendBid() {

const price = document.getElementById('bidInput').value;

fetch(`/api/bids/${auctionId}`, {

method: 'POST',

headers: {'Content-Type': 'application/json'},

body: JSON.stringify({ price: parseFloat(price), token: userToken })

})

.then(response => response.json())

.then(data => {

if (data.error) {

alert(data.error);

} else {

auctionEndTime = Math.floor(Date.now() / 1000) + auctionDuration;

}

});

}



socket.on('new_bid', (data) => {

document.getElementById('lowestBid').innerText = `Najniższa oferta: ${data.price} zł`;

auctionEndTime = Math.floor(Date.now() / 1000) + data.newDuration;

});



socket.on('update_rankings', (data) => {

if (data.rankings && data.rankings[myName] !== undefined) {

document.getElementById('myRank').innerText = "Twoja pozycja: " + data.rankings[myName];

} else {

document.getElementById('myRank').innerText = "Twoja pozycja: --";

}

});


// admin.js

// Inicjalizacja Socket.IO
const socket = io();

// Funkcja wyświetlająca powiadomienia przy użyciu SweetAlert2 (modal)
function showAlert(message, icon = 'success') {
  return Swal.fire({
    icon: icon,
    title: message,
    // Usuwamy opcję toast i ustawienia pozycji, aby modal pojawił się na środku
    showConfirmButton: true
  });
}

// Funkcja generowania zaproszenia
function generateInvitation(auction_id) {
  const userName = document.getElementById("invite_user").value;
  if (!userName) {
    showAlert("Podaj imię użytkownika.", "error");
    return;
  }
  
  fetch(`/send_invitation/${auction_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_name: userName })
  })
  .then(response => response.json())
  .then(data => {
    if (data.error) {
      showAlert(data.error, "error");
    } else {
      // Kopiowanie linku do schowka
      navigator.clipboard.writeText(data.link);
      // Wyświetlamy modal na środku z określonym komunikatem
      Swal.fire({
        icon: 'success',
        title: 'Zaproszenie skopiowano do schowka. Link znajdziesz również na poniższej liście.',
        showConfirmButton: true
      }).then(() => {
        // Po zamknięciu modala ustawiamy hash i przeładowujemy stronę, aby pozostać w zakładce "Zaproszenia"
        window.location.hash = "invitations";
        location.reload();
      });
    }
  })
  .catch(error => {
    console.error("Błąd przy generowaniu zaproszenia:", error);
    showAlert("Wystąpił błąd przy generowaniu zaproszenia.", "error");
  });
}

// Funkcja resetowania aukcji
function resetAuction(auction_id) {
  fetch(`/reset_auction/${auction_id}`, { method: "POST" })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert("Aukcja została zresetowana.", "success").then(() => {
        location.reload();
      });
    } else {
      showAlert("Wystąpił problem podczas resetowania aukcji.", "error");
    }
  })
  .catch(error => {
    console.error("Błąd przy resetowaniu aukcji:", error);
    showAlert("Wystąpił błąd przy resetowaniu aukcji.", "error");
  });
}

// Funkcja kończenia aukcji
function endAuction(auction_id) {
  fetch(`/end_auction/${auction_id}`, { method: "POST" })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showAlert("Aukcja została zakończona.", "success").then(() => {
        location.reload();
      });
    } else {
      showAlert("Wystąpił problem podczas kończenia aukcji.", "error");
    }
  })
  .catch(error => {
    console.error("Błąd przy kończeniu aukcji:", error);
    showAlert("Wystąpił błąd przy kończeniu aukcji.", "error");
  });
}

// Nasłuchiwanie zdarzeń Socket.IO
socket.on('new_bid', (data) => {
  const lowestBidEl = document.getElementById("lowestBid");
  if (lowestBidEl) {
    lowestBidEl.innerText = `Najniższa oferta: ${data.price} zł`;
  }
});

socket.on('update_rankings', (data) => {
  const myRankEl = document.getElementById("myRank");
  // Załóżmy, że zmienna myName jest zdefiniowana w szablonie
  if (data.rankings && data.rankings[myName] !== undefined) {
    myRankEl.innerText = "Twoja pozycja: " + data.rankings[myName];
  } else {
    myRankEl.innerText = "Twoja pozycja: --";
  }
});

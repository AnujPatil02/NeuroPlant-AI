// Service worker — handles push events, shows browser notification
self.addEventListener('push', function(event) {
    const data = event.data.json();
    const options = {
        body: data.body,
        icon: data.icon || '/icons/alert-icon.png',
        badge: '/icons/badge.png',
        data: { machine_id: data.machine_id },
        requireInteraction: true,  // stays visible until dismissed for critical alerts
    };
    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow('/dashboard')  // opens Streamlit dashboard on click
    );
});
package com.atakmap.android.houndmaster.plugin;

import android.os.Bundle;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import com.atakmap.android.chat.ChatManagerMapComponent;
import com.atakmap.android.maps.MapItem;
import com.atakmap.android.maps.MapView;

public class BloodhoundOrderManager implements ChatManagerMapComponent.ChatMessageListener {
    private static final BloodhoundOrderManager INSTANCE = new BloodhoundOrderManager();
    private final List<BloodhoundOrder> orders = new ArrayList<>();
    private final List<OrderChangeListener> listeners = new ArrayList<>();
    private MapView mapView;

    public interface OrderChangeListener {
        void onOrdersChanged();
    }

    public synchronized void initialize(MapView mapView) {
        this.mapView = mapView;
    }

    public synchronized void addOrderChangeListener(OrderChangeListener listener) {
        listeners.add(listener);
    }

    public synchronized void removeOrderChangeListener(OrderChangeListener listener) {
        listeners.remove(listener);
    }

    private void notifyOrderChange() {
        List<OrderChangeListener> listenerSnapshot;
        synchronized (this) {
            listenerSnapshot = new ArrayList<>(listeners);
        }
        for (OrderChangeListener l : listenerSnapshot) {
            l.onOrdersChanged();
        }
    }

    private BloodhoundOrderManager() {}

    public static BloodhoundOrderManager getInstance() {
        return INSTANCE;
    }

    public synchronized void addOrder(BloodhoundOrder order) {
        orders.add(order);
        notifyOrderChange();
    }

    public synchronized void removeOrder(BloodhoundOrder order) {
        orders.remove(order);
        notifyOrderChange();
    }

    public synchronized List<BloodhoundOrder> getOrders() {
        refreshMapItemTitles();
        return new ArrayList<>(orders);
    }

    public synchronized BloodhoundOrder findOrder(String mapItemTitle, String contact) {
        for (BloodhoundOrder order : orders) {
            if (order.getMapItemTitle().equals(mapItemTitle) && order.getContact().equals(contact)) {
                return order;
            }
        }
        return null;
    }

    @Override
    public void chatMessageReceived(Bundle message) {
        String text = message.getString("message");
        if (text == null) {
            return;
        }

        StatusUpdate update = getStatusUpdate(text);
        if (update == null) {
            return;
        }

        String normalizedText = text.toLowerCase(Locale.ROOT);
        String senderUid = message.getString("senderUid");
        // ATAK also reports this device's own outgoing chats, including the order prompt.
        if (senderUid != null && senderUid.equals(MapView.getDeviceUid())) {
            return;
        }
        String conversationId = message.getString("conversationId");
        String senderCallsign = message.getString("senderCallsign");
        synchronized (this) {
            boolean titlesChanged = refreshMapItemTitles();
            BloodhoundOrder matchedOrder = null;
            boolean matchedByUid = false;
            BloodhoundOrder senderOnlyCandidate = null;
            int senderOnlyCount = 0;
            boolean hasSenderMetadata = senderUid != null || conversationId != null
                    || senderCallsign != null;
            for (BloodhoundOrder order : orders) {
                boolean senderMatches = senderMatches(order, senderUid, conversationId,
                        senderCallsign);
                boolean legacyTextMatches = !hasSenderMetadata
                        && containsWholeValue(normalizedText, order.getContact());
                if (!senderMatches && !legacyTextMatches) {
                    continue;
                }

                if (senderMatches && order.getStatus() != BloodhoundOrder.Status.Complete) {
                    senderOnlyCandidate = order;
                    senderOnlyCount++;
                }

                String targetUid = order.getMapItemUid();
                boolean targetUidMatches = targetUid != null
                        && containsWholeValue(normalizedText, targetUid);
                boolean targetTitleMatches = containsWholeValue(normalizedText, order.getMapItemTitle());
                if (!targetUidMatches && !targetTitleMatches) {
                    continue;
                }

                if (targetUidMatches) {
                    if (matchedByUid) {
                        if (titlesChanged) {
                            notifyOrderChange();
                        }
                        return;
                    }
                    matchedOrder = order;
                    matchedByUid = true;
                } else if (!matchedByUid) {
                    if (matchedOrder != null) {
                        if (titlesChanged) {
                            notifyOrderChange();
                        }
                        return;
                    }
                    matchedOrder = order;
                }
            }

            // Short replies like "RGR" name no target; accept them only when the
            // sender has exactly one open order.
            if (matchedOrder == null && senderOnlyCount == 1) {
                matchedOrder = senderOnlyCandidate;
            }

            if (matchedOrder != null && matchedOrder.getStatus() != update.status) {
                matchedOrder.setStatus(update.status);
                notifyOrderChange();
            } else if (titlesChanged) {
                notifyOrderChange();
            }
        }
    }

    private boolean senderMatches(BloodhoundOrder order, String senderUid,
            String conversationId, String senderCallsign) {
        String contactUid = order.getContactUid();
        if (senderUid != null) {
            return contactUid != null && contactUid.equals(senderUid);
        }
        boolean conversationMatches = conversationId != null && contactUid != null
                && contactUid.equals(conversationId);
        boolean callsignMatches = senderCallsign != null && order.getContact() != null
                && senderCallsign.equalsIgnoreCase(order.getContact());
        return conversationMatches || callsignMatches;
    }

    private StatusUpdate getStatusUpdate(String text) {
        String normalized = text.toLowerCase(Locale.ROOT);
        boolean rgr = containsWholeValue(normalized, "rgr")
                || containsWholeValue(normalized, "roger");
        boolean nPos = containsWholeValue(normalized, "npos");
        // A message carrying both short codes is the order prompt itself, not a reply.
        if (rgr && nPos) {
            return null;
        }
        if (normalized.contains("bloodhounding") || normalized.contains("bloodhonding") || rgr) {
            return new StatusUpdate(BloodhoundOrder.Status.Bloodhounding);
        }
        if (normalized.contains("in position") || nPos) {
            return new StatusUpdate(BloodhoundOrder.Status.Complete);
        }
        return null;
    }

    private boolean containsWholeValue(String normalizedText, String value) {
        if (value == null || value.isEmpty()) {
            return false;
        }

        String normalizedValue = value.toLowerCase(Locale.ROOT);
        int index = normalizedText.indexOf(normalizedValue);
        while (index >= 0) {
            int end = index + normalizedValue.length();
            boolean startsAtBoundary = index == 0
                    || !Character.isLetterOrDigit(normalizedText.charAt(index - 1));
            boolean endsAtBoundary = end == normalizedText.length()
                    || !Character.isLetterOrDigit(normalizedText.charAt(end));
            if (startsAtBoundary && endsAtBoundary) {
                return true;
            }
            index = normalizedText.indexOf(normalizedValue, index + 1);
        }
        return false;
    }

    private boolean refreshMapItemTitles() {
        if (mapView == null) {
            return false;
        }

        boolean changed = false;
        for (BloodhoundOrder order : orders) {
            String uid = order.getMapItemUid();
            MapItem mapItem = uid == null ? null : mapView.getMapItem(uid);
            String currentTitle = mapItem == null ? null : mapItem.getTitle();
            if (currentTitle != null && !currentTitle.equals(order.getMapItemTitle())) {
                order.setMapItemTitle(currentTitle);
                changed = true;
            }
        }
        return changed;
    }

    private static final class StatusUpdate {
        private final BloodhoundOrder.Status status;

        private StatusUpdate(BloodhoundOrder.Status status) {
            this.status = status;
        }
    }
}

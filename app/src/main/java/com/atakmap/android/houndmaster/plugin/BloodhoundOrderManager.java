package com.atakmap.android.houndmaster.plugin;

import android.os.Bundle;

import java.util.ArrayList;
import java.util.List;

import com.atakmap.android.chat.ChatManagerMapComponent;

public class BloodhoundOrderManager implements ChatManagerMapComponent.ChatMessageListener {
    private static final BloodhoundOrderManager INSTANCE = new BloodhoundOrderManager();
    private final List<BloodhoundOrder> orders = new ArrayList<>();

    // Listener interface and support
    public interface OrderChangeListener {
        void onOrdersChanged();
    }
    private final List<OrderChangeListener> listeners = new ArrayList<>();

    public void addOrderChangeListener(OrderChangeListener listener) {
        listeners.add(listener);
    }

    public void removeOrderChangeListener(OrderChangeListener listener) {
        listeners.remove(listener);
    }

    private void notifyOrderChange() {
        for (OrderChangeListener l : listeners) {
            l.onOrdersChanged();
        }
    }

    private BloodhoundOrderManager() {}

    public static BloodhoundOrderManager getInstance() {
        return INSTANCE;
    }

    public void addOrder(BloodhoundOrder order) {
        orders.add(order);
        notifyOrderChange();
    }

    public void removeOrder(BloodhoundOrder order) {
        orders.remove(order);
        notifyOrderChange();
    }

    public List<BloodhoundOrder> getOrders() {
        return orders;
    }

    public BloodhoundOrder findOrder(String mapItemTitle, String contact) {
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

        String senderUid = message.getString("senderUid");
        String conversationId = message.getString("conversationId");
        String senderCallsign = message.getString("senderCallsign");
        BloodhoundOrder matchedOrder = null;
        for (BloodhoundOrder order : orders) {
            if (!text.toLowerCase().contains(order.getMapItemTitle().toLowerCase())) {
                continue;
            }

            boolean senderMatches = senderMatches(order, senderUid, conversationId, senderCallsign);
            boolean legacyTextMatches = senderUid == null && conversationId == null
                    && senderCallsign == null
                    && text.toLowerCase().contains(order.getContact().toLowerCase());
            if (senderMatches || legacyTextMatches) {
                if (matchedOrder != null) {
                    return;
                }
                matchedOrder = order;
            }
        }

        if (matchedOrder != null && matchedOrder.getStatus() != update.status) {
            matchedOrder.setStatus(update.status);
            notifyOrderChange();
        }
    }

    private boolean senderMatches(BloodhoundOrder order, String senderUid,
            String conversationId, String senderCallsign) {
        String contactUid = order.getContactUid();
        return (senderUid != null && contactUid != null && contactUid.equals(senderUid))
                || (conversationId != null && contactUid != null
                && contactUid.equals(conversationId))
                || (senderCallsign != null
                && senderCallsign.equalsIgnoreCase(order.getContact()));
    }

    private StatusUpdate getStatusUpdate(String text) {
        String normalized = text.toLowerCase();
        if (normalized.contains("bloodhounding") || normalized.contains("bloodhonding")) {
            return new StatusUpdate(BloodhoundOrder.Status.Bloodhounding);
        }
        if (normalized.contains("in position")) {
            return new StatusUpdate(BloodhoundOrder.Status.Complete);
        }
        return null;
    }

    private static final class StatusUpdate {
        private final BloodhoundOrder.Status status;

        private StatusUpdate(BloodhoundOrder.Status status) {
            this.status = status;
        }
    }
}

package com.atakmap.android.houndmaster.plugin;

public class BloodhoundOrder {
    private String mapItemTitle;
    private final String mapItemUid;
    private final String contact;
    private final String contactUid;
    private Status status;

    public enum Status {
        Sent,
        Bloodhounding,
        Complete
    }

    public BloodhoundOrder(String mapItemTitle, String contact, Status status) {
        this(mapItemTitle, null, contact, null, status);
    }

    public BloodhoundOrder(String mapItemTitle, String contact, String contactUid, Status status) {
        this(mapItemTitle, null, contact, contactUid, status);
    }

    public BloodhoundOrder(String mapItemTitle, String mapItemUid, String contact,
            String contactUid, Status status) {
        this.mapItemTitle = mapItemTitle;
        this.mapItemUid = mapItemUid;
        this.contact = contact;
        this.contactUid = contactUid;
        this.status = status;
    }

    public String getMapItemTitle() {
        return mapItemTitle;
    }

    public String getMapItemUid() {
        return mapItemUid;
    }

    public void setMapItemTitle(String mapItemTitle) {
        // Keep the original title if the map item is temporarily unavailable.
        if (mapItemTitle != null && !mapItemTitle.isEmpty()) {
            this.mapItemTitle = mapItemTitle;
        }
    }

    public String getContact() {
        return contact;
    }

    public String getContactUid() {
        return contactUid;
    }

    public Status getStatus() {
        return status;
    }

    public void setStatus(Status status) {
        this.status = status;
    }
}

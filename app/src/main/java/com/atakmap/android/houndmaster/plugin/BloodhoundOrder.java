package com.atakmap.android.houndmaster.plugin;

public class BloodhoundOrder {
    private final String mapItemTitle;
    private final String contact;
    private Status status;

    public enum Status {
        Sent,
        Bloodhounding,
        Complete
    }

    public BloodhoundOrder(String mapItemTitle, String contact, Status status) {
        this.mapItemTitle = mapItemTitle;
        this.contact = contact;
        this.status = status;
    }

    public String getMapItemTitle() {
        return mapItemTitle;
    }

    public String getContact() {
        return contact;
    }

    public Status getStatus() {
        return status;
    }

    public void setStatus(Status status) {
        this.status = status;
    }
}


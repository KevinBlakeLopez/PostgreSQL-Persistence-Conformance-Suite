package org.ppcs.hibernate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** Marker row in the runner's {@code item} table. Not a domain model. */
@Entity
@Table(name = "item")
public class Item {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "qty", nullable = false)
    private int qty;

    public Item() {}

    public Item(String name) {
        this.name = name;
        this.qty = 0;
    }

    public Integer getId() {
        return id;
    }

    public String getName() {
        return name;
    }
}

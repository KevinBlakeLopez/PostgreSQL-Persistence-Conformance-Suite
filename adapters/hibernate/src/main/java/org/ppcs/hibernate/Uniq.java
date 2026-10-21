package org.ppcs.hibernate;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** Row in the runner's {@code uniq} table. The fixture already holds {@code taken}. */
@Entity
@Table(name = "uniq")
public class Uniq {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Integer id;

    @Column(name = "code", nullable = false, unique = true)
    private String code;

    public Uniq() {}

    public Uniq(String code) {
        this.code = code;
    }

    public String getCode() {
        return code;
    }
}

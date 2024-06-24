# -*- coding: utf-8 -*-

"""
/***************************************************************************
Name                 : D'Hondt Calculator
Description          : Script that calculates seats for constituencies vector layer with votes and seats data
Date                 : 24/Jun/2024
copyright            : (C) 2024 by Kamil Iwaniuk
email                : iwaniukkamil@gmail.com
reference:
***************************************************************************/

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingException,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterField,
                       QgsProcessingParameterNumber,
                       QgsAggregateCalculator, QgsFields, QgsField, QgsFeature)
from qgis import processing


class DHondtProcessingAlgorithm(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    VOTES = 'VOTES'
    VOTES_PARTIES = 'VOTES_PARTIES'
    THRESHOLD = 'THRESHOLD'
    SEATS_COUNT = 'SEATS_COUNT'
    OUTPUT = 'OUTPUT'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return DHondtProcessingAlgorithm()

    def name(self):
        return 'dhondtcalculator'

    def displayName(self):
        return self.tr("D'Hondt calculator")

    def group(self):
        return self.tr("Political tools")

    def groupId(self):
        return 'politicaltools'

    def shortHelpString(self):
        return self.tr("Script that calculates seats for constituencies vector layer with votes and seats data.")

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        
        self.addParameter(
            QgsProcessingParameterField(
                self.VOTES,
                self.tr('Column with total vote count'),
                '',
                self.INPUT
            )
        )
        
        self.addParameter(
            QgsProcessingParameterField(
                self.VOTES_PARTIES,
                self.tr('Columns with votes for parties'),
                '',
                self.INPUT,
                allowMultiple = True
            )
        )
        
        self.addParameter(
            QgsProcessingParameterNumber(
                self.THRESHOLD,
                self.tr('Value of electoral threshold (set 0 if none)'),
                QgsProcessingParameterNumber.Double,
                0
            )
        )
        
        self.addParameter(
            QgsProcessingParameterField(
                self.SEATS_COUNT,
                self.tr('Column with count of seats by region'),
                '',
                self.INPUT
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):

        source = self.parameterAsSource(
            parameters,
            self.INPUT,
            context
        )

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        total = 100.0 / source.featureCount() if source.featureCount() else 0
        features = source.getFeatures()
        
        total_votes = self.parameterAsFields(
            parameters,
            self.VOTES,
            context
        )
        
        parties_columns = self.parameterAsFields(
            parameters,
            self.VOTES_PARTIES,
            context
        )
        
        electoral_threshold = self.parameterAsDouble(
            parameters,
            self.THRESHOLD,
            context
        )
        
        layer = self.parameterAsLayer(
            parameters,
            self.INPUT,
            context
        )
        
        seats = self.parameterAsFields(
            parameters,
            self.SEATS_COUNT,
            context
        )
        
        total_votes_sum = layer.aggregate(QgsAggregateCalculator.Sum, total_votes[0])[0]
        parties = []
        
        for party in parties_columns:
            party_votes_sum = layer.aggregate(QgsAggregateCalculator.Sum, party)[0]
            if ( party_votes_sum / total_votes_sum ) * 100 > electoral_threshold:
                parties.append(party)

        if not parties:
            parties = parties_columns
        
        table = QgsFields(source.fields())
        for p in parties:
            field = QgsField(f'SEATS_{p}',QVariant.Int)
            table.append(field)
        
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            table,
            source.wkbType(),
            source.sourceCrs()
        )

        feedback.pushInfo('CRS is {}'.format(source.sourceCrs().authid()))

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        for current, feature in enumerate(features):
            if feedback.isCanceled():
                break
            
            output_object = QgsFeature( table )
            geom = feature.geometry()
            output_object.setGeometry(geom)
            
            seat_limit = feature[seats[0]]
            votes_sum = [feature[party] for party in parties]
            mandates = [0 for party in parties]
            
            for i in range(0, seat_limit):
                max_value = -1
                max_index = -1
                for p in parties:
                    party_index = parties.index(p)
                    temp_value = int(votes_sum[party_index] / (mandates[party_index]+1))
                    if temp_value > max_value or temp_value == max_value and votes_sum[party_index] > votes_sum[max_index]:
                        max_value = temp_value
                        max_index = party_index
                if max_index >= 0:
                    mandates[max_index] += 1

            attributes = feature.attributes()
            for p in parties:
                party_index = parties.index(p)
                attributes.append(mandates[party_index])
            
            output_object.setAttributes(attributes)
            
            sink.addFeature(output_object, QgsFeatureSink.FastInsert)

            feedback.setProgress(int(current * total))

        if False:
            buffered_layer = processing.run("native:buffer", {
                'INPUT': dest_id,
                'DISTANCE': 1.5,
                'SEGMENTS': 5,
                'END_CAP_STYLE': 0,
                'JOIN_STYLE': 0,
                'MITER_LIMIT': 2,
                'DISSOLVE': False,
                'OUTPUT': 'memory:'
            }, context=context, feedback=feedback)['OUTPUT']

        return {self.OUTPUT: dest_id}
